"""
Every instance is built around a planted full tiling, so a full-coverage
layout exists for each one by construction. Checks are purely geometric:
ids, bounds, aspect band, min area, pairwise overlap, total coverage.
"""
import pytest

from instance_gen import build_instance
from verify import verify_placement
import lib

# Aspect ratios are pinned (band of +-0.01%), so each block has one free scale.
# The planted tilings contain pinwheel (non-guillotine) structure, so they cannot
# be produced by recursive straight cuts of the canvas.
# Area floors are 88-97% of the planted rectangle's area, drawn independently
# per block with no category label, and the coverage
# threshold is 0.999, so blocks must grow past their floors and the scales
# have to be solved jointly for the layout to close.
PARAMS = dict(aspect_tolerance=0.0001, min_fracs=(0.97, 0.93, 0.88),
              coverage_threshold=0.999, tiling="hierarchical", pinwheel_prob=0.6)

STANDARD_SEEDS = [189, 255, 339, 375, 296, 207, 383]   # 15 blocks
LARGE_SEEDS = [148, 102, 58]                           # 15 blocks


def _guillotine(rs, eps=1e-6):
    """True if the rectangles can be separated by recursive straight cuts."""
    if len(rs) <= 1:
        return True
    for lo, ext in ((0, 2), (1, 3)):
        cuts = sorted({round(r[lo], 6) for r in rs} | {round(r[lo] + r[ext], 6) for r in rs})
        for c in cuts[1:-1]:
            if all(r[lo] + r[ext] <= c + eps or r[lo] >= c - eps for r in rs):
                a = [r for r in rs if r[lo] + r[ext] <= c + eps]
                b = [r for r in rs if r[lo] >= c - eps]
                return _guillotine(a) and _guillotine(b)
    return False


@pytest.mark.parametrize("seed", STANDARD_SEEDS + LARGE_SEEDS)
def test_graded_tilings_are_not_guillotine(seed):
    _, planted = build_instance(1000, 1000, seed=seed, target_blocks=12, **PARAMS)
    rects = [(p["x"], p["y"], p["width"], p["height"]) for p in planted]
    assert not _guillotine(rects)


def test_verifier_rejects_overlap():
    inst, planted = build_instance(1000, 1000, seed=1, target_blocks=12, **PARAMS)
    bad = [dict(p) for p in planted]
    bad[1]["x"], bad[1]["y"] = bad[0]["x"], bad[0]["y"]
    ok, _, _ = verify_placement(inst, bad)
    assert not ok


def test_verifier_rejects_aspect_violation():
    inst, planted = build_instance(1000, 1000, seed=2, target_blocks=12, **PARAMS)
    bad = [dict(p) for p in planted]
    bad[0]["width"] *= 0.5
    ok, _, _ = verify_placement(inst, bad)
    assert not ok


def test_verifier_rejects_low_coverage():
    inst, planted = build_instance(1000, 1000, seed=3, target_blocks=12, **PARAMS)
    ok, _, _ = verify_placement(inst, planted[:-1])
    assert not ok


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), True, "0"])
def test_verifier_rejects_non_finite_or_non_numeric(bad_value):
    inst, planted = build_instance(1000, 1000, seed=2, target_blocks=12, **PARAMS)
    bad = [dict(p) for p in planted]
    bad[0]["x"] = bad_value
    ok, _, _ = verify_placement(inst, bad)
    assert not ok


def test_verifier_rejects_all_nan_layout():
    inst, planted = build_instance(1000, 1000, seed=2, target_blocks=12, **PARAMS)
    nan = float("nan")
    bad = [{"id": p["id"], "x": nan, "y": nan,
            "width": p["width"] * 1.01, "height": p["height"] * 1.01}
           for p in planted]
    ok, _, _ = verify_placement(inst, bad)
    assert not ok


def test_verifier_accepts_planted_tiling():
    inst, planted = build_instance(1000, 1000, seed=2, target_blocks=12, **PARAMS)
    ok, reason, coverage = verify_placement(inst, planted)
    assert ok, reason
    assert coverage > 0.999


@pytest.mark.parametrize("seed", STANDARD_SEEDS)
def test_standard_instance(seed):
    inst, _ = build_instance(1000, 1000, seed=seed, target_blocks=12, **PARAMS)
    lib.check(inst, time_limit_seconds=60)


@pytest.mark.parametrize("seed", LARGE_SEEDS)
def test_large_instance(seed):
    inst, _ = build_instance(1000, 1000, seed=seed, target_blocks=12, **PARAMS)
    lib.check(inst, time_limit_seconds=120)
