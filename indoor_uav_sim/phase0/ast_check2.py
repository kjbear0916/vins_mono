import ast, sys
path = sys.argv[1] if len(sys.argv) > 1 else '/mnt/d/Things/indoor_uav_sim/phase0/rssi_positioning_node.py'
with open(path, encoding='utf-8') as f:
    source = f.read()
ast.parse(source)
print('AST OK')
