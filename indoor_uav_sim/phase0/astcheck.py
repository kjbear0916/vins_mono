import ast
import sys

p = sys.argv[1]
with open(p, encoding="utf-8", newline="") as f:
    ast.parse(f.read())
print("AST_OK")