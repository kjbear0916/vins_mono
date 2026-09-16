import numpy as np, math, time, sys
sys.path.insert(0, '/mnt/d/Things/indoor_uav_sim/phase0')
from rssi_positioning_node import (DEFAULT_APS, rssi_measurement, rssi_to_distance,
                                   trilaterate, distance_to_rssi, SyntheticPoseSource,
                                   KalmanFilterXYZ, P0_DBM, PATH_LOSS)

rng = np.random.default_rng(seed=1234)
srcc = SyntheticPoseSource()
est = KalmanFilterXYZ(0.2, [15.0,15.0,40.0])
first = True
prev_pred = None
t0 = time.monotonic()
for step in range(120):
    true = srcc.get()
    gt = np.array(true)
    rssi = rssi_measurement(DEFAULT_APS, gt, rng)
    dists = [rssi_to_distance(r) for r in rssi]
    x_fix, res = trilaterate(DEFAULT_APS, dists)
    if x_fix is None or res > 25:
        print(f"{step:3d} REJECTED res={res:.1f}")
        continue
    if first:
        est.init(x_fix)
        first = False
        print(f"{step:3d} INIT fix={x_fix} res={res:.1f}")
        continue
    est_xyz = est.update(x_fix)
    if step < 25 or step % 10 == 0:
        print(f"{step:3d} true=({gt[0]:5.2f},{gt[1]:5.2f},{gt[2]:5.2f}) fix=({x_fix[0]:5.2f},{x_fix[1]:5.2f},{x_fix[2]:5.2f}) "
              f"est=({est_xyz[0]:5.2f},{est_xyz[1]:5.2f},{est_xyz[2]:5.2f}) res={res:.1f}")