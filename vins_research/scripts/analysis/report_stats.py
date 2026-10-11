#!/usr/bin/env python3
"""Summary stats for the paired master vs repo54 matrix: scale-gate counts,
time-valid paired ATE diffs, and time-valid RTF distribution.
"""
import csv
import statistics as st

MASTER_SCALE = "/data/results/scale_sweep.csv"
RERUN_SCALE = "/data/results_rerun54/scale_sweep_repo54.csv"
PAIRED = "/data/results_rerun54/paired_master_repo54.csv"


def scales(path):
    d = {}
    for r in csv.DictReader(open(path, newline="")):
        try:
            d[r["trial_id"].replace("_repo54", "")] = float(r["sim3_scale"])
        except (KeyError, ValueError, TypeError):
            pass
    return d


def in_gate(v):
    return 0.96 <= v <= 1.03


def main():
    m = scales(MASTER_SCALE)
    r = scales(RERUN_SCALE)
    m["high_1.5ms_circle_r1"] = 1.0303  # manual sim3 from rep2 trajectories
    inter = sorted(set(m) & set(r))
    agree = sum(1 for k in inter if in_gate(m[k]) == in_gate(r[k]))

    def count(d):
        return (sum(1 for v in d.values() if in_gate(v)),
                sum(1 for v in d.values() if v < 0.96),
                sum(1 for v in d.values() if v > 1.03))

    mg, mud, mov = count(m)
    rg, rud, rov = count(r)
    print("scale index %.3f..%.3f" % (0.96, 1.03))
    print("  master n=%d  in-gate=%d (%.1f%%)  under=%d  over=%d  max=%.3f"
          % (len(m), mg, 100.0 * mg / len(m), mud, mov, max(m.values())))
    print("  rerun  n=%d  in-gate=%d (%.1f%%)  under=%d  over=%d  max=%.3f"
          % (len(r), rg, 100.0 * rg / len(r), rud, rov, max(r.values())))
    print("  gate agreement on %d shared cells: %d agree, %d disagree"
          % (len(inter), agree, len(inter) - agree))
    for k in inter:
        if in_gate(m[k]) != in_gate(r[k]):
            print("    disagree %s  master=%.3f  rerun=%.3f" % (k, m[k], r[k]))

    diffs = []
    ntv = []
    for row in csv.DictReader(open(PAIRED, newline="")):
        if not row["diff"]:
            continue
        d = float(row["diff"])
        w = float(row["wall_s"])
        rf = float(row["rtf"])
        if not (0.3 <= rf <= 3.0 and 100 <= w <= 1200):
            ntv.append("%s(rtf=%s,wall=%s)" % (row["cell"].split()[0] if row["cell"] else "",
                                               row["rtf"], row["wall_s"]))
            continue
        diffs.append(d)
    if diffs:
        print("\npaired ATE diff (repo54 - master), time-valid cells n=%d" % len(diffs))
        print("  median=%+.3f  mean=%+.3f  min=%+.3f  max=%+.3f"
              % (st.median(diffs), st.mean(diffs), min(diffs), max(diffs)))
        within = sum(1 for d in diffs if abs(d) <= 0.14)
        print("  |d|<=0.14 noise: %d/%d (%.0f%%)" % (within, len(diffs),
                                                     100.0 * within / len(diffs)))
        big = [d for d in diffs if abs(d) > 0.14]
        if big:
            big.sort()
            print("  |d|>0.14: %d cells  min=%.3f max=%.3f  pos-count=%d neg-count=%d"
                  % (len(big), min(big), max(big),
                     sum(1 for x in big if x > 0), sum(1 for x in big if x < 0)))
    else:
        print("\nno time-valid diffs")
    if ntv:
        print("  excluded non-time-valid (%d): %s" % (len(ntv), "; ".join(ntv)))

    rt = []
    for row in csv.DictReader(open(PAIRED, newline="")):
        w = float(row["wall_s"])
        rf = float(row["rtf"])
        if 100 <= w <= 1200 and 0.3 <= rf <= 3.0:
            rt.append(rf)
    if rt:
        print("\nRTF time-valid n=%d  median=%.3f  min=%.3f  max=%.3f"
              % (len(rt), st.median(rt), min(rt), max(rt)))
        lo = sorted(x for x in rt if x < 0.3)
        if lo:
            print("  RTF<0.3: %d (%s)" % (len(lo), ", ".join("%.3f" % x for x in lo)))


if __name__ == "__main__":
    main()