
x: int = int(input())
y: int = int(input())
# list1 -> (O@0:4), sum -> O, x -> U, y -> N
list1: List[int] = [1, x, 2, 3, 5, 8, y]
sum: int = 0

sum: int = sum + list1[2]
sum: int = sum + list1[1]
sum: int = sum + list1[4]
sum: int = sum + list1[3]
sum: int = sum + list1[0]

print(sum)