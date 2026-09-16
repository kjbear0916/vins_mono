import re, statistics

errs_xy, errs_3d = [], []
z_true, z_est = [], []
with open('/tmp/sim_run.log') as f:
    for line in f:
        m = re.search(r'errXY=\s*([0-9.]+)m err3D=\s*([0-9.]+)m', line)
        if m:
            errs_xy.append(float(m.group(1)))
            errs_3d.append(float(m.group(2)))
        m2 = re.search(r'true=\(\s*([0-9.\-]+)\s*,\s*([0-9.\-]+)\s*,\s*([0-9.\-]+)\s*\)\s+est\s*=\(([0-9.\-]+)\s*,\s*([0-9.\-]+)\s*,\s*([0-9.\-]+)\)', line)
        if m2:
            z_true.append(float(m2.group(3)))
            z_est.append(float(m2.group(6)))

def stats(v):
    v = sorted(v)
    n = len(v)
    return (round(v[int(n*0.5)],2), round(v[int(n*0.9)],2), round(sum(v)/n,2))

print(f"n={len(errs_xy)}")
print("XY err median/p90/mean:", stats(errs_xy))
print("3D err median/p90/mean:", stats(errs_3d))
print(f"z_true={z_true[0] if z_true else '?'} z_est sample: {z_est[:6] if z_est else '?'}")