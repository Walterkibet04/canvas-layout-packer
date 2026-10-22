Place a list of rectangular blocks on a fixed canvas. You choose each block's width, height and position.

Run as `/app/start.sh <path-to-instance.json>`. The environment variable `TIME_LIMIT_SECONDS` is your time budget. Print one JSON object to stdout and exit, with one entry per block id:

```
{"placements": [{"id": "b0", "x": 12.0, "y": 0.0, "width": 180.5, "height": 240.0}, ...]}
```

Anything else you print should go to stderr. If you cannot find a valid layout in time, print an empty or partial list; it scores nothing, but do not run past your budget.

The instance file looks like this:

```json
{
  "canvas": {"width": 1000, "height": 1000},
  "coverage_threshold": 0.999,
  "blocks": [
    {"id": "b0", "target_aspect_ratio": 1.4,
     "aspect_tolerance": 0.0001, "min_area": 74000}
  ]
}
```

A layout is valid when all of the following hold:

- Every block id appears exactly once.
- Every rectangle lies completely inside the canvas.
- No two rectangles overlap; sharing an edge is fine.
- Each block's width divided by height is between `target_aspect_ratio * (1 - aspect_tolerance)` and `target_aspect_ratio * (1 + aspect_tolerance)`.
- Each block's width times height is at least `min_area`.
- The total area of all rectangles divided by the canvas area is at least `coverage_threshold`.

A valid layout exists for every instance. Expect about 15 to 17 blocks on a canvas of about 1000 units per side. Any valid layout gets full credit.

Only `/app` is carried into grading, which runs in a separate container with bare Python 3.12 and no network access. Anything beyond the standard library has to be vendored into `/app`.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
