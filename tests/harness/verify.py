"""Pure geometric verification of a placement against an instance."""
import math


def _is_finite_number(v):
    # bool is an int subclass; reject it. Reject NaN/inf, which make every
    # comparison below silently False.
    return (
        isinstance(v, (int, float))
        and not isinstance(v, bool)
        and math.isfinite(v)
    )


def rects_overlap(a, b, eps=1e-6):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ox = min(ax + aw, bx + bw) - max(ax, bx)
    oy = min(ay + ah, by + bh) - max(ay, by)
    return ox > eps and oy > eps


def verify_placement(instance, placements, eps=1e-6):
    """Returns (ok, reason, coverage)."""
    cw = instance["canvas"]["width"]
    ch = instance["canvas"]["height"]
    blocks = {b["id"]: b for b in instance["blocks"]}

    if len(placements) != len(blocks):
        return False, f"expected {len(blocks)} placements, got {len(placements)}", 0.0

    if not isinstance(placements, list):
        return False, "placements is not a list", 0.0

    seen, rects = set(), []
    for p in placements:
        if not isinstance(p, dict):
            return False, "placement entry is not an object", 0.0
        pid = p.get("id")
        if not isinstance(pid, str):
            return False, f"invalid block id {pid!r}", 0.0
        if pid not in blocks:
            return False, f"unknown block id {pid!r}", 0.0
        if pid in seen:
            return False, f"duplicate placement for {pid!r}", 0.0
        seen.add(pid)
        vals = [p.get(k) for k in ("x", "y", "width", "height")]
        if not all(_is_finite_number(v) for v in vals):
            return False, f"{pid}: non-finite or non-numeric geometry", 0.0
        x, y, w, h = vals
        if w <= 0 or h <= 0:
            return False, f"{pid}: non-positive dimension", 0.0
        if x < -eps or y < -eps or x + w > cw + eps or y + h > ch + eps:
            return False, f"{pid}: out of canvas bounds", 0.0
        b = blocks[pid]
        aspect = w / h
        lo = b["target_aspect_ratio"] * (1 - b["aspect_tolerance"])
        hi = b["target_aspect_ratio"] * (1 + b["aspect_tolerance"])
        if not (lo - 1e-6 <= aspect <= hi + 1e-6):
            return False, f"{pid}: aspect {aspect:.4f} outside [{lo:.4f}, {hi:.4f}]", 0.0
        if w * h < b["min_area"] - 1e-6:
            return False, f"{pid}: area {w*h:.2f} below min_area {b['min_area']:.2f}", 0.0
        rects.append((x, y, w, h))

    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if rects_overlap(rects[i], rects[j], eps):
                return False, f"overlap between {placements[i]['id']} and {placements[j]['id']}", 0.0

    coverage = sum(w * h for _, _, w, h in rects) / (cw * ch)
    if not math.isfinite(coverage):
        return False, "non-finite coverage", 0.0
    threshold = instance.get("coverage_threshold", 0.95)
    if coverage < threshold - 1e-6:
        return False, f"coverage {coverage:.4f} below required {threshold:.4f}", coverage
    return True, "ok", coverage
