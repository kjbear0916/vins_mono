import numpy as np, math

APS = [(0.0,0.0,2.5),(8.0,0.0,2.5),(8.0,8.0,2.5),(0.0,8.0,2.5)]
P0_DBM, PATH_LOSS, RSSI_NOISE_SIGMA = -40.0, 2.2, 3.0

def rssi_to_distance(rssi_db):
    return 10.0 ** ((P0_DBM - rssi_db) / (10.0 * PATH_LOSS))

def distance_to_rssi(distance):
    return P0_DBM - 10.0 * PATH_LOSS * math.log10(max(distance, 1e-6))

def trilaterate(aps, distances, x0=None):
    aps = np.asarray(aps, dtype=float)
    distances = np.asarray(distances, dtype=float)
    if x0 is None:
        x = aps.mean(axis=0)
    else:
        x = np.asarray(x0, dtype=float).copy()
    lam = 0.1
    for _ in range(30):
        r = np.linalg.norm(aps - x, axis=1)
        r = np.maximum(r, 0.5)
        f = r - distances
        J = (x - aps) / r[:, None]
        try:
            A = J.T @ J + lam * np.eye(3)
            b = -J.T @ f
            dx = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            break
        x = x + dx
        if np.linalg.norm(dx) < 1e-6:
            break
    r = np.linalg.norm(aps - x, axis=1); r = np.maximum(r,0.5)
    f = r - distances; res = np.linalg.norm(f)
    if not np.all(np.isfinite(x)):
        return None, None
    return x, res

rng = np.random.default_rng(seed=7)
# evaluate over a grid of true positions INSIDE the AP square
xs = np.arange(0.5, 8.0, 1.0)
ys = np.arange(0.5, 8.0, 1.0)
grid = np.array([[x, y, 1.0] for x in xs for y in ys])

errs = []
res_vals = []
for gt in grid:
    for _ in range(20):
        rssi = [distance_to_rssi(np.linalg.norm(gt-a)) + rng.normal(0, RSSI_NOISE_SIGMA) for a in APS]
        dists = [rssi_to_distance(r) for r in rssi]
        est, resid = trilaterate(APS, dists)
        if est is None:
            continue
        errs.append(np.linalg.norm(est - gt))
        res_vals.append(resid)

errs = np.array(errs); res_vals = np.array(res_vals)
for th in [0, 2.0, 3.0, 4.0, 5.0]:
    mask = res_vals <= th
    if mask.sum():
        print(f"resid<={th}: n={mask.sum()} xy_med={np.median(np.linalg.norm(np.array(grid_med),axis=1)) if False else ''} "
              f"3d_med={np.median(errs[mask]):.2f} 3d_mean={np.mean(errs[mask]):.2f} p90={np.percentile(errs[mask],90):.2f}")
print(f"no gate: n={len(errs)} 3d_med={np.median(errs):.2f} p90={np.percentile(errs,90):.2f}")