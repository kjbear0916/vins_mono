"""Fly-inspired looming detector core (LPLC2-inspired, numpy only).

Implements a reduced functional model of the Drosophila looming-detection
circuit: a compound-eye-like mosaic (block-mean retina), elementary motion
detectors in the four cardinal directions (Hassenstein-Reichardt correlators
on ON/OFF channels), optic-flow divergence extraction, and a population of
radial-motion-opponency units (LPLC2-style) that collectively vote on the
presence and image position of an approaching (looming) object.

No rclpy / cv2 imports: intended to be unit-testable on the host and used by
the thin ROS wrapper node.
"""
import math

import numpy as np


def _block_mean(a: np.ndarray, nx: int, ny: int) -> np.ndarray:
    h, w = a.shape
    bh, bw = h // ny, w // nx
    if bh == 0 or bw == 0:
        raise ValueError(f"requested grid {nx}x{ny} bigger than frame {w}x{h}")
    cropped = a[: bh * ny, : bw * nx].astype(np.float32)
    return cropped.reshape(ny, bh, nx, bw).mean(axis=(1, 3))


def _smooth(m: np.ndarray, sigma: float) -> np.ndarray:
    radius = max(1, int(round(3 * sigma)))
    x = np.arange(-radius, radius + 1)
    kernel = np.exp(-(x ** 2) / (2.0 * sigma ** 2))
    kernel = kernel / kernel.sum()
    out = m.astype(np.float32)
    for axis in (0, 1):
        out = np.apply_along_axis(
            lambda row: np.convolve(row, kernel, mode="same"), axis, out
        )
    return out


def _relu(m: np.ndarray) -> np.ndarray:
    return np.clip(m, 0.0, None)


def _robust_max(m: np.ndarray, q: float = 0.99) -> float:
    flat = m[m > 0].ravel()
    if flat.size == 0:
        return 0.0
    return float(np.quantile(flat, q))


class LoomingDetector:
    """Reduced LPLC2-inspired looming detector over a coarse visual mosaic."""

    def __init__(
        self,
        nx: int = 24,
        ny: int = 18,
        rf_size: int = 7,
        rf_spacing: int = 4,
        beta: float = 0.5,
        sigma: float = 1.2,
        leak: float = 0.6,
        frame_period: float = 1.0 / 15.0,
    ):
        self.nx = nx
        self.ny = ny
        self.rf_half = rf_size // 2
        self.rf_spacing = rf_spacing
        self.beta = beta
        self.sigma = sigma
        self.leak = leak
        self.frame_period = frame_period

        self.src_w = None
        self.src_h = None
        self.fx = None
        self.fy = None

        self._prev = None
        self._score = 0.0

    def configure_geometry(self, src_w: int, src_h: int, hfov: float):
        self.src_w = int(src_w)
        self.src_h = int(src_h)
        self.fx = (self.src_w / 2.0) / np.tan(hfov / 2.0)
        self.fy = self.fx * (self.src_h / float(self.src_w))

    def _unit_centers(self):
        m = self.rf_half
        cxs = np.arange(m, self.nx - m, self.rf_spacing)
        cys = np.arange(m, self.ny - m, self.rf_spacing)
        return cxs, cys

    def _emd_maps(self, cur, prev):
        sh_l = {"cur": np.roll(cur, -1, axis=1), "prev": np.roll(prev, -1, axis=1)}
        sh_r = {"cur": np.roll(cur, 1, axis=1), "prev": np.roll(prev, 1, axis=1)}
        sh_d = {"cur": np.roll(cur, -1, axis=0), "prev": np.roll(prev, -1, axis=0)}
        sh_u = {"cur": np.roll(cur, 1, axis=0), "prev": np.roll(prev, 1, axis=0)}

        hr_r = cur * sh_l["prev"] - sh_l["cur"] * prev
        hr_l = cur * sh_r["prev"] - sh_r["cur"] * prev
        hr_d = cur * sh_d["prev"] - sh_d["cur"] * prev
        hr_u = cur * sh_u["prev"] - sh_u["cur"] * prev

        v_r = _smooth(_relu(hr_r), self.sigma)
        v_l = _smooth(_relu(hr_l), self.sigma)
        v_d = _smooth(_relu(hr_d), self.sigma)
        v_u = _smooth(_relu(hr_u), self.sigma)
        return v_r, v_l, v_d, v_u

    def _normalize(self, maps):
        stacked = np.stack(list(maps), axis=0)
        ref = _robust_max(stacked)
        if ref <= 1e-6:
            return tuple(np.zeros_like(m) for m in maps), 0.0
        return tuple(m / ref for m in maps), ref

    def _lplc2_pool(self, v_r, v_l, v_d, v_u):
        cxs, cys = self._unit_centers()
        pool = np.zeros((cys.size, cxs.size), dtype=np.float32)
        m = self.rf_half
        dy, dx = np.mgrid[-m : m + 1, -m : m + 1].astype(np.float32)
        r = np.sqrt(dx * dx + dy * dy) + 1e-6
        rx, ry = dx / r, dy / r
        out_sum = 0.0
        in_sum = 0.0
        vote = 0.0
        for j, cy in enumerate(cys):
            for i, cx in enumerate(cxs):
                w_r = v_r[cy - m : cy + m + 1, cx - m : cx + m + 1]
                w_l = v_l[cy - m : cy + m + 1, cx - m : cx + m + 1]
                w_d = v_d[cy - m : cy + m + 1, cx - m : cx + m + 1]
                w_u = v_u[cy - m : cy + m + 1, cx - m : cx + m + 1]
                rdot = w_r * rx - w_l * rx + w_d * ry - w_u * ry
                outward = _relu(rdot)
                inward = _relu(-rdot)
                out = float(outward.sum())
                inn = float(inward.sum())
                out_sum += out
                in_sum += inn
                iso = 1.0 - math.hypot(
                    float((outward * rx).sum()), float((outward * ry).sum())
                ) / (out + 1e-6)
                resp = max(0.0, out - self.beta * inn) * max(0.0, iso)
                pool[j, i] = resp
                vote += resp
        return pool, vote, out_sum, in_sum

    def process(self, gray: np.ndarray, hfov: float = None, dt: float = None) -> dict:
        result = {
            "score": 0.0,
            "azimuth": 0.0,
            "elevation": 0.0,
            "expansion": 0.0,
            "active": False,
        }
        if gray is None:
            return result

        src_h, src_w = gray.shape[:2]
        if self.src_w is None or self.src_w != src_w:
            self.configure_geometry(src_w, src_h, hfov or (80.0 * np.pi / 180.0))

        grid = _block_mean(gray.astype(np.float32), self.nx, self.ny)

        if self._prev is None:
            self._prev = grid
            return result

        cur, prev = grid, self._prev
        self._prev = cur

        v_r, v_l, v_d, v_u = self._emd_maps(cur, prev)
        (v_r, v_l, v_d, v_u), _ = self._normalize((v_r, v_l, v_d, v_u))

        div = (v_r - v_l) + (v_d - v_u)

        d_pos = float(_relu(div).mean())
        d_neg = float(_relu(-div).mean())
        denom = d_pos + d_neg
        div_signed = 0.0 if denom <= 1e-6 else (d_pos - d_neg) / denom

        pool, vote, out_sum, in_sum = self._lplc2_pool(v_r, v_l, v_d, v_u)

        eff = vote / (out_sum + 1e-6)
        rad_bias = min(1.0, max(0.0, (eff - 0.06) / 0.3))

        raw = max(0.0, div_signed) * min(1.0, 0.15 + 0.85 * rad_bias)
        saturated = raw / (raw + 0.12)

        period = dt if dt is not None else self.frame_period
        alpha = self.leak ** (period / self.frame_period)
        self._score = alpha * self._score + (1.0 - alpha) * float(saturated)

        active_mask = div > 1e-3
        cxg, cyg = None, None
        if active_mask.any():
            weights = _relu(div)[active_mask]
            idxs = np.argwhere(active_mask)
            cxg = float((idxs[:, 1] * weights).sum() / weights.sum())
            cyg = float((idxs[:, 0] * weights).sum() / weights.sum())
            px = ((cxg + 0.5) / self.nx) * self.src_w
            py = ((cyg + 0.5) / self.ny) * self.src_h
            result["azimuth"] = float(np.arctan2((px - self.src_w / 2.0) / self.fx, 1.0))
            result["elevation"] = float(np.arctan2((py - self.src_h / 2.0) / self.fy, 1.0))

        result["score"] = float(np.clip(self._score, 0.0, 1.0))
        result["expansion"] = float(d_pos)
        result["active"] = result["score"] > 0.0
        return result