
x1: str = input()
x2: str = input()
# STATE: x -> String, x1 -> Integer, x2 -> Integer, y -> Float
x: str = x1 + x2
# STATE: x -> Integer, x1 -> String, x2 -> String, y -> Float
y: float = int(x)
# FINAL: x -> String, x1 -> String, x2 -> String, y -> Float
