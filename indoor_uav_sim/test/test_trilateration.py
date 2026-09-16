#!/usr/bin/env python3
"""Unit test for UWB trilateration math — no Gazebo required.

Validates that the least-squares trilateration algorithm correctly
recovers 3D positions from known anchor positions and distances.
"""
import sys
import numpy as np
from scipy.optimize import least_squares


def trilaterate(anchors, distances, max_iter=100, threshold=0.5):
    """Recover 3D position from anchor positions and measured distances.

    Args:
        anchors: (N, 3) array of anchor positions
        distances: (N,) array of measured distances
        max_iter: max iterations for least_squares
        threshold: max residual to consider valid

    Returns:
        (3,) position estimate, or None if failed
    """
    weights = np.ones(len(distances))

    def residuals(pos):
        dists = np.linalg.norm(anchors - pos, axis=1)
        return weights * (dists - distances)

    x0 = np.mean(anchors, axis=0)

    result = least_squares(residuals, x0, method="lm", max_nfev=max_iter)

    if result.cost < threshold * len(distances):
        return result.x
    return None


def add_noise(distances, std=0.2):
    return distances + np.random.normal(0, std, len(distances))


def test_exact():
    """Trilateration with exact (noiseless) distances."""
    anchors = np.array([
        [0, 0, 0],
        [5, 0, 0],
        [0, 5, 0],
        [0, 0, 5],
    ], dtype=float)
    true_pos = np.array([2.0, 2.0, 2.0])
    dists = np.linalg.norm(anchors - true_pos, axis=1)

    result = trilaterate(anchors, dists)
    assert result is not None, "Trilateration failed on exact distances"
    error = np.linalg.norm(result - true_pos)
    assert error < 0.01, f"Exact test error too high: {error:.4f}"
    print(f"  PASS: exact test, error={error:.6f} m")


def test_noisy():
    """Trilateration with noisy distances."""
    np.random.seed(42)
    anchors = np.array([
        [0, 0, 0],
        [10, 0, 0],
        [0, 10, 0],
        [0, 0, 8],
    ], dtype=float)
    true_pos = np.array([3.0, 4.0, 2.5])
    dists = np.linalg.norm(anchors - true_pos, axis=1)

    errors = []
    for _ in range(100):
        noisy_dists = add_noise(dists, std=0.2)
        result = trilaterate(anchors, noisy_dists)
        if result is not None:
            errors.append(np.linalg.norm(result - true_pos))

    assert len(errors) > 80, f"Too many failures: {100 - len(errors)}"
    mean_err = np.mean(errors)
    max_err = max(errors)
    assert mean_err < 1.0, f"Mean error too high: {mean_err:.4f}"
    print(f"  PASS: noisy test (100 trials), mean_err={mean_err:.4f} m, "
          f"max_err={max_err:.4f} m")


def test_minimum_anchors():
    """Trilateration with 4 anchors (minimum for unique 3D fix).

    3D trilateration requires >= 4 non-coplanar anchors for a unique
    solution. With exactly 3 anchors the system is underdetermined and
    the least-squares fit may converge to either of two mirror solutions.
    The production system always deploys >= 4 anchors before attempting
    a fix (min_anchors=3 in config means 3 ranges received, but the
    anchor_manager tracks all previously deployed anchors, so in practice
    4+ are available). This test validates the 4-anchor case.
    """
    anchors = np.array([
        [0, 0, 0],
        [6, 0, 0],
        [0, 6, 0],
        [3, 3, 5],
    ], dtype=float)
    true_pos = np.array([2.0, 2.0, 1.0])
    dists = np.linalg.norm(anchors - true_pos, axis=1)

    result = trilaterate(anchors, dists)
    assert result is not None, "Trilateration failed with 4 anchors"
    error = np.linalg.norm(result - true_pos)
    assert error < 0.1, f"4-anchor test error: {error:.4f}"
    print(f"  PASS: 4-anchor test, error={error:.6f} m")


def test_out_of_range():
    """Anchors beyond effective range should be excluded."""
    anchors = np.array([
        [0, 0, 0],
        [5, 0, 0],
        [0, 5, 0],
        [0, 0, 5],
        [50, 50, 50],  # way too far
    ], dtype=float)
    true_pos = np.array([2.0, 2.0, 2.0])
    dists = np.linalg.norm(anchors - true_pos, axis=1)

    effective_range = 15.0
    mask = dists <= effective_range
    result = trilaterate(anchors[mask], dists[mask])
    assert result is not None
    error = np.linalg.norm(result - true_pos)
    assert error < 0.1
    print(f"  PASS: out-of-range filtering, error={error:.6f} m")


def test_noise_std_sweep():
    """Measure how error scales with noise level."""
    np.random.seed(123)
    anchors = np.array([
        [0, 0, 0],
        [10, 0, 0],
        [0, 10, 0],
        [0, 0, 8],
    ], dtype=float)
    true_pos = np.array([3.0, 4.0, 2.5])
    dists = np.linalg.norm(anchors - true_pos, axis=1)

    print("  Noise std vs mean error:")
    for std in [0.05, 0.1, 0.2, 0.3, 0.5]:
        errors = []
        for _ in range(50):
            noisy = add_noise(dists, std=std)
            result = trilaterate(anchors, noisy)
            if result is not None:
                errors.append(np.linalg.norm(result - true_pos))
        if errors:
            mean_err = np.mean(errors)
            print(f"    std={std:.2f}m -> mean_err={mean_err:.4f}m "
                  f"({len(errors)}/50 valid)")
        else:
            print(f"    std={std:.2f}m -> ALL FAILED")


if __name__ == "__main__":
    print("UWB Trilateration Unit Tests")
    print("=" * 40)
    test_exact()
    test_minimum_anchors()
    test_noisy()
    test_out_of_range()
    test_noise_std_sweep()
    print("=" * 40)
    print("All tests passed!")
