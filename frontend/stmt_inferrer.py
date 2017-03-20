"""Inferrer for python statements.

Infers the types for the following expressions:
    - Assign(expr* targets, expr value)

    TODO:
    - Return(expr? value)
    - Delete(expr* targets)
    - AugAssign(expr target, operator op, expr value)
    - AnnAssign(expr target, expr annotation, expr? value, int simple)
    - For(expr target, expr iter, stmt* body, stmt* orelse)
    - AsyncFor(expr target, expr iter, stmt* body, stmt* orelse)
    - While(expr test, stmt* body, stmt* orelse)
    - If(expr test, stmt* body, stmt* orelse)
    - With(withitem* items, stmt* body)
    - AsyncWith(withitem* items, stmt* body)
    - Raise(expr? exc, expr? cause)
    - Try(stmt* body, excepthandler* handlers, stmt* orelse, stmt* finalbody)
    - Assert(expr test, expr? msg)
    - Import(alias* names)
    - ImportFrom(identifier? module, alias* names, int? level)
    - Global(identifier* names)
    - Nonlocal(identifier* names)
    - Expr(expr value)
    - Pass | Break | Continue
"""

import expr_inferrer as expr, ast
from context import Context
from i_types import *

def __infer_assignment_target(target, context, value_type):
    """Infer the type of a target in an assignment

    Attributes:
        target: the target whose type is to be inferred
        context: the current context level
        value_type: the type of the value assigned to the target

    Target cases:
        - Variable name. Ex: x = 1
        - Tuple. Ex: a, b = 1, "string"
        - List. Ex: [a, b] = [1, "string"]
        - Subscript. Ex: x[0] = 1, x[1 : 2] = [2,3], x["key"] = value
        - Compound: Ex: a, b[0], [c, d], e["key"] = 1, 2.0, [True, False], "value"

    Limitation:
        - In case of tuple/list assignments, there are no guarantees for correct number of unpacked values.
            Because the length of the list/tuple may not be resolved statically.
    """
    if isinstance(target, ast.Name):
        if context.has_variable(target.id): # Check if variable is already inferred before
            var_type = context.get_type(target.id)
            if var_type.is_subtype(value_type):
                context.set_type(target.id, value_type)
            elif not value_type.is_subtype(var_type):
                raise TypeError("The type of {} is {}. Cannot assign it to {}.".format(target.id,
                                                                                    var_type.get_name(),
                                                                                    value_type.get_name()))
        else:
            context.set_type(target.id, value_type)
    elif isinstance(target, ast.Tuple) or isinstance(target, ast.List): # Tuple/List assignment
        if not expr.is_sequence(value_type):
            raise ValueError("Cannot unpack a non sequence.")
        for i in range(len(target.elts)):
            seq_elem = target.elts[i]
            if isinstance(value_type, TString):
                infer_assignment_target(seq_elem, context, value_type)
            elif isinstance(value_type, TList):
                infer_assignment_target(seq_elem, context, value_type.type)
            elif isinstance(value_type, TTuple):
                infer_assignment_target(seq_elem, context, value_type.types[i])
    elif isinstance(target, ast.Subscript): # Subscript assignment
        subscript_type = expr.infer(target, context)
        indexed_type = expr.infer(target.value, context)
        if isinstance(indexed_type, TString):
            raise TypeError("String objects don't support item assignment.")
        elif isinstance(indexed_type, TList):
            if isinstance(target.slice, ast.Index):
                if indexed_type.type.is_subtype(value_type): # Update the type of the list with the more generic type
                    if isinstance(target.value, ast.Name):
                        context.set_type(target.value.id, TList(value_type))
                elif not value_type.is_subtype(indexed_type.type):
                    raise TypeError("Cannot assign {} to {}.".format(value_type.get_name(), indexed_type.type.get_name()))
            else: # Slice subscripting
                if indexed_type.is_subtype(value_type):
                    if isinstance(target.value, ast.Name): # Update the type of the list with the more generic type
                        context.set_type(target.value.id, value_type)
                elif not (isinstance(value_type, TList) and value_type.type.is_subtype(indexed_type.type)):
                    raise TypeError("Cannot assign {} to {}.".format(value_type.get_name(), indexed_type.get_name()))
        elif isinstance(indexed_type, TDictionary):
            if indexed_type.value_type.is_subtype(value_type):
                if isinstance(target.value, ast.Name): # Update the type of the dictionary values with the more generic type
                    context.get_type(target.value.id).value_type = value_type
            elif not value_type.is_subtype(indexed_type.value_type):
                raise TypeError("Cannot assign {} to a dictionary item of type {}.".format(value_type.get_name(), indexed_type.value_type.get_name()))
        elif isinstance(indexed_type, TTuple):
            # TODO: implement tuple subscripting assignment
            pass

    else:
        raise ValueError("Cannot assign value to a literal.")

def _infer_assign(node, context):
    """Infer the types of target variables in an assignment node."""
    value_type = expr.infer(node.value, context) # The type of the value assigned to the targets in the assignment statement.
    for target in node.targets:
        __infer_assignment_target(target, context, value_type)

    return TNone()

def infer(node, context):
    if isinstance(node, ast.Assign):
        return _infer_assign(node, context)
    return TNone()
