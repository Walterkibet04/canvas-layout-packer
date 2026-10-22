"""
Generates a planted layout instance: start from a full tiling of the
canvas built by recursively subdividing rectangles (mixing ordinary 2-way
splits with 5-piece pinwheel splits, which no single straight cut can
separate), then derive each block's declared constraints (target aspect
ratio, tolerance band, minimum area) from its planted dimensions with
enough slack that the planted dimensions always satisfy them. A
full-coverage solution therefore exists for every instance regardless of
any solver.
"""
import random


def _pinwheel_5(x0, y0, w, h, rng):
    a = x0 + rng.uniform(0.25, 0.45) * w
    c = x0 + rng.uniform(0.55, 0.75) * w
    b = y0 + rng.uniform(0.25, 0.45) * h
    d = y0 + rng.uniform(0.55, 0.75) * h
    x1, y1 = x0 + w, y0 + h
    return [
        (x0, y0, c - x0, b - y0),
        (c, y0, x1 - c, d - y0),
        (a, d, x1 - a, y1 - d),
        (x0, b, a - x0, y1 - b),
        (a, b, c - a, d - b),
    ]


def _split_2way(x0, y0, w, h, rng):
    frac = rng.uniform(0.35, 0.65)
    if w >= h:
        cut = w * frac
        return [(x0, y0, cut, h), (x0 + cut, y0, w - cut, h)]
    cut = h * frac
    return [(x0, y0, w, cut), (x0, y0 + cut, w, h - cut)]


MIN_DIM_FRACTION = 0.06


def generate_tiling(canvas_w, canvas_h, rng, target_blocks, pinwheel_prob=0.35):
    rects = [(0.0, 0.0, float(canvas_w), float(canvas_h))]
    min_w = canvas_w * MIN_DIM_FRACTION
    min_h = canvas_h * MIN_DIM_FRACTION
    while len(rects) < target_blocks:
        splittable = [i for i, (x, y, w, h) in enumerate(rects)
                      if w > min_w * 2.2 and h > min_h * 2.2]
        if not splittable:
            break
        idx = max(splittable, key=lambda i: rects[i][2] * rects[i][3])
        x, y, w, h = rects.pop(idx)
        use_pinwheel = (rng.random() < pinwheel_prob
                        and w > min_w * 3.2 and h > min_h * 3.2
                        and len(rects) + 5 <= target_blocks + 4)
        rects.extend(_pinwheel_5(x, y, w, h, rng) if use_pinwheel
                     else _split_2way(x, y, w, h, rng))
    return rects


def generate_generic_tiling(canvas_w, canvas_h, rng, target_blocks):
    """Random gap-free dissection built by repeatedly filling the lowest open
    corner of a skyline with a random rectangle. The result has no recursive
    split or pinwheel hierarchy: edges end in T-junctions all over the canvas."""
    cw, ch = float(canvas_w), float(canvas_h)
    md = 0.07 * min(cw, ch)
    avg = cw * ch / target_blocks
    sky = [[0.0, cw, 0.0]]
    rects = []
    while True:
        open_ = [i for i, sg in enumerate(sky) if sg[2] < ch - 1e-9]
        if not open_:
            break
        j = min(open_, key=lambda i: (sky[i][2], sky[i][0]))
        x0, x1, y0 = sky[j]
        W, A = x1 - x0, ch - y0
        if W < 2.2 * md or rng.random() < 0.3:
            w = W
        else:
            w = rng.uniform(0.3, 0.7) * W
            w = min(max(w, md), W - md)
        if A < 2.2 * md:
            h = A
        else:
            h = avg / w * rng.uniform(0.7, 1.4)
            h = min(max(h, md), A)
            if A - h < md:
                h = A
        rects.append((x0, y0, w, h))
        new = [[x0, x0 + w, y0 + h]]
        if x1 - (x0 + w) > 1e-9:
            new.append([x0 + w, x1, y0])
        sky = sky[:j] + new + sky[j + 1:]
        merged = []
        for sg in sky:
            if merged and abs(merged[-1][2] - sg[2]) < 1e-9:
                merged[-1][1] = sg[1]
            else:
                merged.append(sg)
        sky = merged
    return rects


DEFAULT_MIN_FRACS = (0.80, 0.70, 0.55)


def build_instance(canvas_w, canvas_h, seed, target_blocks=14,
                   aspect_tolerance=0.12, pinwheel_prob=0.35,
                   min_fracs=DEFAULT_MIN_FRACS, coverage_threshold=0.95,
                   tiling="hierarchical"):
    rng = random.Random(seed)
    if tiling == "generic":
        rects = generate_generic_tiling(canvas_w, canvas_h, rng, target_blocks)
    else:
        rects = generate_tiling(canvas_w, canvas_h, rng, target_blocks, pinwheel_prob)
    # Each block gets its own area-floor fraction drawn from the full range, and
    # carries no category label, so the floors reveal nothing about the hidden
    # rectangle areas beyond a loose bound.
    frac_rng = random.Random(seed * 104729 + 31)
    lo_f, hi_f = min(min_fracs), max(min_fracs)
    entries = [(frac_rng.uniform(lo_f, hi_f), r) for r in rects]
    # Shuffle with an independent RNG and assign ids afterwards, so neither
    # block order nor ids reveal which pieces came from the same split.
    random.Random(seed * 7919 + 104729).shuffle(entries)
    blocks, planted = [], []
    for i, (frac, (x, y, w, h)) in enumerate(entries):
        blocks.append({
            "id": f"b{i}",
            "target_aspect_ratio": round(w / h, 6),
            "aspect_tolerance": aspect_tolerance,
            "min_area": round(w * h * frac, 3),
        })
        planted.append({"id": f"b{i}", "x": x, "y": y, "width": w, "height": h})
    instance = {
        "canvas": {"width": canvas_w, "height": canvas_h},
        "coverage_threshold": coverage_threshold,
        "blocks": blocks,
    }
    return instance, planted
