#!/usr/bin/env python3
import csv, re, glob, statistics, os

def load_sum(path):
    rows = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            key = (r["light"], r["speed"], r["trajectory"], r["repeat"])
            rows[key] = r
    return rows

master = load_sum("/data/results/summary_54.csv")
repo54 = load_sum("/data/results_rerun54/summary_54.csv")
imu    = load_sum("/data/results_imu161/summary_54.csv")

def load_scale_sweep(path, strip_suffix=""):
    out = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            tid = r["trial_id"]
            if strip_suffix and tid.endswith(strip_suffix):
                tid = tid[: -len(strip_suffix)]
            out[tid] = float(r["sim3_scale"]) if r["sim3_scale"] else None
    return out

sc_m = load_scale_sweep("/data/results/scale_sweep.csv")
sc_r = load_scale_sweep("/data/results_rerun54/scale_sweep_repo54.csv", "_repo54")

imu_scales = {}
for lp in glob.glob("/tmp/trial_*_imu161.log"):
    tid = os.path.basename(lp).replace("trial_", "").replace(".log", "")
    m = re.search(r"SIM3 scale=([0-9.]+)", open(lp).read())
    if m:
        imu_scales[tid] = float(m.group(1))

CELLS = [("high","0.5","circle"),("high","1.5","figure8"),
         ("medium","1.5","circle"),("medium","3.0","figure8"),
         ("low","1.5","figure8"),("low","3.0","circle")]
REPS = ["r1","r2","r3"]
GATE = (0.960, 1.030)
NOISE = 0.14

print(f'{"cell":>22} {"rep":>3} | {"ATE_imu":>8} {"ATE_m":>8} {"ATE_r":>8} | {"dM":>7} {"dR":>7} | {"hz":>6} {"rtf":>6} | {"s_imu":>6} {"s_m":>6} {"s_r":>6} | gate_imu | notes')
for c in CELLS:
    for rep in REPS:
        k = (*c, rep)
        i = imu.get(k); m = master.get(k); r = repo54.get(k)
        def g(r): return f'{float(r["ate_rms"]):.3f}' if r else "----"
        a_i = float(i["ate_rms"]) if i else None
        a_m = float(m["ate_rms"]) if m else None
        a_r = float(r["ate_rms"]) if r else None
        dM = (a_i - a_m) if (a_i is not None and a_m is not None) else None
        dR = (a_i - a_r) if (a_i is not None and a_r is not None) else None
        tid = i["trial_id"] if i else ""
        s_i = imu_scales.get(tid)
        s_m = sc_m.get(tid.replace("_imu161",""))
        s_r = sc_r.get(tid.replace("_imu161",""))
        gate_i = (GATE[0] <= s_i <= GATE[1]) if s_i else None
        notes = []
        if dM is not None and abs(dM) > NOISE: notes.append(f"|dM|>0.14")
        if dR is not None and abs(dR) > NOISE: notes.append(f"|dR|>0.14")
        if gate_i is False: notes.append("scale<0.96")
        if s_m and not (GATE[0] <= s_m <= GATE[1]): notes.append("smOG")
        if s_r and not (GATE[0] <= s_r <= GATE[1]): notes.append("srOG")
        hz = i["imu_hz"] if i else "----"
        rtf = i["rtf"] if i else "----"
        g_gate = "in" if gate_i else ("out" if gate_i is False else "?")
        print(f'{f"{c[0]}/{c[1]}/{c[2]}":>22} {rep:>3} | {g(i):>8} {g(m):>8} {g(r):>8} | {dM:>7.3f} ' if False else
              f'{f"{c[0]}/{c[1]}/{c[2]}":>22} {rep:>3} | {g(i):>8} {g(m):>8} {g(r):>8} | {f"{dM:.3f}" if dM is not None else "----":>7} {f"{dR:.3f}" if dR is not None else "----":>7} | {hz:>6} {rtf:>6} | {f"{s_i:.4f}" if s_i else "----":>6} {f"{s_m:.4f}" if s_m else "----":>6} {f"{s_r:.4f}" if s_r else "----":>6} | {g_gate:>7} | {",".join(notes)}')

def arm_stats(d):
    d = {k: r for k, r in d.items() if k in imu}          # same 18 subset cells only
    ates = [float(r["ate_rms"]) for r in d.values()]
    rtfs = [float(r.get("rtf", 0)) for r in d.values()]
    hzs  = [float(r.get("imu_hz", 0)) for r in d.values()]
    def md(x): return f"{statistics.median(x):.3f}" if x else "n/a"
    return (f'cells={len(d)} ok={sum(1 for r in d.values() if r.get("features_note")=="ok")}'
            f' fail={sum(1 for r in d.values() if r.get("features_note")!="ok")}'
            f' medianATE={md(ates)}')

print()
print("ARM 50Hz master :", arm_stats(master))
print("ARM 50Hz repo54 :", arm_stats(repo54))
print("ARM imu161(~125):", arm_stats(imu))

# imu161 overall median RTF / hz and gate counts
hz_all = sorted(float(r["imu_hz"]) for r in imu.values())
rtf_all = sorted(float(r["rtf"]) for r in imu.values())
print(f"imu161 imu_hz: min={hz_all[0]:.1f} median={statistics.median(hz_all):.1f} max={hz_all[-1]:.1f}")
print(f"imu161 rtf   : min={rtf_all[0]:.3f} median={statistics.median(rtf_all):.3f} max={rtf_all[-1]:.3f}")
sg = [v for v in imu_scales.values() if GATE[0] <= v <= GATE[1]]
print(f"imu161 scale-gate: {len(sg)}/{len(imu_scales)} in [{GATE[0]},{GATE[1]}]  (out: {[k+'='+str(round(imu_scales[k],4)) for k in imu_scales if not (GATE[0]<=imu_scales[k]<=GATE[1])]})")