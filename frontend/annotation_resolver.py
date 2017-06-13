from z3 import Or
import ast


class AnnotationResolver:
    """Resolver for type annotations in functions"""
    def __init__(self, z3_types):
        self.z3_types = z3_types
        self.primitives = {
            "object": z3_types.object,
            "int": z3_types.int,
            "bool": z3_types.bool,
            "float": z3_types.float,
            "complex": z3_types.complex,
            "str": z3_types.string,
            "bytes": z3_types.bytes,
            "None": z3_types.none,
            "number": z3_types.num,
            "sequence": z3_types.seq
        }
        self.type_vars = {}

    def resolve(self, annotation, solver, generics_map=None):
        """Resolve the type annotation with the following grammar:
        
        :param annotation: the type annotation to be resolved
        :param solver: the SMT solver for the program
        :param generics_map: Optional map that maps generic types names to their types in a specific function call
                
        t = object | int | bool | float | complex | str | bytes | None
            | List[t]
            | Dict[t, t]
            | Set[t]
            | Type[t]
            | Tuple[t*]
            | Callable[[t*], t]
        """
        if isinstance(annotation, ast.Name):
            if annotation.id in self.primitives:
                return self.primitives[annotation.id]
            if annotation.id in self.z3_types.all_types:
                return getattr(self.z3_types.type_sort, "class_{}".format(annotation.id))
            
            # Check if it's a generic type var
            if generics_map is None:
                raise ValueError("Invalid type annotation {} in line {}".format(annotation.id, annotation.lineno))
            if annotation.id in generics_map:
                return generics_map[annotation.id]
            if annotation.id not in self.type_vars:
                raise ValueError("Invalid type annotation {} in line {}".format(annotation.id, annotation.lineno))

            result_type = solver.new_z3_const("generic")
            generics_map[annotation.id] = result_type
            supers_types = [self.resolve(x, solver, generics_map) for x in self.type_vars[annotation.id]]
            solver.add([solver.z3_types.subtype(result_type, x) for x in supers_types])
            return result_type

        if isinstance(annotation, ast.Subscript):
            assert isinstance(annotation.value, ast.Name)
            assert isinstance(annotation.slice, ast.Index)
            annotation_val = annotation.value.id
            if annotation_val == "List":
                # Parse List type
                return self.z3_types.list(self.resolve(annotation.slice.value, solver, generics_map))
            
            if annotation_val == "Dict":
                # Parse Dict type
                assert isinstance(annotation.slice.value, ast.Tuple)
                assert len(annotation.slice.value.elts) == 2

                # Get the types of the dict args
                keys_type = self.resolve(annotation.slice.value.elts[0], solver, generics_map)
                vals_type = self.resolve(annotation.slice.value.elts[1], solver, generics_map)
                return self.z3_types.dict(keys_type, vals_type)
            
            if annotation_val == "Set":
                # Parse Set type
                return self.z3_types.set(self.resolve(annotation.slice.value, solver, generics_map))
            
            if annotation_val == "Type":
                # Parse Type type
                return self.z3_types.type(self.resolve(annotation.slice.value, solver, generics_map))
            
            if annotation_val == "Tuple":
                # Parse Tuple type
                assert isinstance(annotation.slice.value, (ast.Name, ast.Tuple))

                # Get the types of the tuple args
                if isinstance(annotation.slice.value, ast.Name):
                    tuple_args_types = [self.resolve(annotation.slice.value, solver, generics_map)]
                else:
                    tuple_args_types = [self.resolve(x, solver, generics_map) for x in annotation.slice.value.elts]
                return self.z3_types.tuples[len(tuple_args_types)](*tuple_args_types)
            
            if annotation_val == "Callable":
                # Parse Callable type
                assert isinstance(annotation.slice.value, ast.Tuple)
                assert len(annotation.slice.value.elts) == 2
                assert isinstance(annotation.slice.value.elts[0], ast.List)

                # Get the args and return types
                args_annotations = annotation.slice.value.elts[0].elts
                args_types = [self.resolve(x, solver, generics_map) for x in args_annotations]
                return_type = self.resolve(annotation.slice.value.elts[1], solver, generics_map)

                return self.z3_types.funcs[len(args_types)](*(args_types + [return_type]))

            if annotation_val == "Union":
                # Parse Union type
                assert isinstance(annotation.slice.value, (ast.Name, ast.Tuple))

                # Get the types of the union args
                if isinstance(annotation.slice.value, ast.Name):
                    union_args_types = [self.resolve(annotation.slice.value, solver, generics_map)]
                else:
                    union_args_types = [self.resolve(x, solver, generics_map) for x in annotation.slice.value.elts]

                # The result of the union type is only one of args, Z3 picks the appropriate one
                # according to the added constraints.
                # Therefore, using more than one type from the union in the same program isn't yet supported.
                # For example, the following is not supported:
                # def f(x: Union[int, str]): ...
                # f(1)
                # f("str")
                result_type = solver.new_z3_const("union")
                solver.add(Or([result_type == arg for arg in union_args_types]),
                           fail_message="Union in type annotation")

                return result_type

        raise ValueError("Invalid type annotation in line {}".format(annotation.lineno))

    def add_annotated_function_axioms(self, args_types, solver, annotations, result_type):
        """Add axioms for a function call to an annotated function
        
        Reprocess the type annotations for every function call to prevent binding a certain type
        to the function definition
        """
        args_annotations = annotations[0]
        result_annotation = annotations[1]

        if len(args_types) != len(args_annotations):
            raise TypeError("The function expects {} arguments. {} were given.".format(len(args_annotations),
                                                                                       len(args_types)))
        generics_map = {}

        for i in range(len(args_annotations)):
            arg_type = self.resolve(args_annotations[i], solver, generics_map)
            solver.add(solver.z3_types.subtype(args_types[i], arg_type),
                       fail_message="Generic parameter type")

        solver.add(result_type == self.resolve(result_annotation, solver, generics_map),
                   fail_message="Generic return type")

    def add_type_var(self, type_var_node):
        if not type_var_node.args.args:
            raise TypeError("Invalid type variable declaration in line {}.".format(type_var_node.lineno))
        args = type_var_node.args.args
        if not isinstance(args[0], ast.Str):
            raise TypeError("Name of type variable in line {} should be a string".format(type_var_node.lineno))
        type_var_name = type_var_node.args.args[0].s

        type_var_supers = []
        if len(args) > 1:
            if not isinstance(args[1], ast.List):
                raise TypeError("Supers of type variable in line {} should be a list".format(type_var_node.lineno))
            type_var_supers = args[1]

        self.type_vars[type_var_name] = type_var_supers
