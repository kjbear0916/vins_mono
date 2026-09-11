"""Gate redundancy / independence analysis on adversarial grid metrics.

Parses adversarial_search.py's *_metrics.csv + *_grid.csv and computes the
pairwise correlation of the gate METRICS (not just PASS/FAIL) so we can tell
how much unique information each gate carries.  High |rho| between two gates
= they track the same underlying failure mode; low = independent.

The point (part of the protocol-criticality write-up): the 7 gates are not 7
independent checks -- several share one dominant-axis / smoothness signal,
which is exactly why the sway blind spot slips through (it is invisible to
every "dominant-axis" gate at once).

Usage:
  python gate_redundancy.py vo/_adv/adv_metrics.csv
"""
import csv
import re
import sys
import numpy as np


def num(s):
    if not s or s in ("-", ""):
        return None
    v = float(s)
    return None if not np.isfinite(v) else v


def extract_numeric(metric):
    """Pull the leading number from a gate detail string."""
    m = re.search(r"([0-9.]+)", str(metric))
    return num(m.group(1)) if m else None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else r"D:\Things\vo\_adv\adv_metrics.csv"
    rows = list(csv.DictReader(open(path, newline="")))
    cols = ["P2", "P3", "P4", "P5", "P6", "P7", "ATEpost"]
    data = {}
    for c in cols:
        data[c] = []
    for r in rows:
        for c in cols:
            data[c].append(extract_numeric(r.get(c)))
    # correlation only over rows where all seven are numeric & non-zero
    X = np.array([data[c] for c in cols], dtype=float).T
    valid = np.all(np.isfinite(X), axis=1)
    X = X[valid]
    print("numeric rows (all 7 present): %d / %d\n" % (len(X), len(rows)))
    if len(X) < 3:
        print("too few complete rows for correlation")
        return
    R = np.corrcoef(X.T)
    fmt = "%-9s" + " %8s" * len(cols)
    print(fmt % (("",) + tuple(cols)))
    for i, c in enumerate(cols):
        print(fmt % ((c,) + tuple("%.2f" % R[i, j] for j in range(len(cols)))))
    print("\ninterpretation:")
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            rr = R[i, j]
            if abs(rr) >= 0.7:
                tag = "REDUNDANT-ish" if rr > 0 else "ANTI-correlated"
                print("  %s~%s rho=%.2f  (%s)" % (cols[i], cols[j], rr, tag))
            elif abs(rr) >= 0.4:
                print("  %s~%s rho=%.2f  (mildly coupled)" % (cols[i], cols[j], rr))


if __name__ == "__main__":
    sys.exit(main())