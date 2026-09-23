import ast, sys
for f in sys.argv[1:]:
    ast.parse(open(f, encoding="utf-8").read())
    print("OK", f)
