"""
Soft-module floorplan solver.

Each block has (almost) a fixed aspect ratio, so its size is one unknown
scale s_i: width = a_i * s_i, height = b_i * s_i, area = s_i**2 >= min_area.
All edge coordinates are therefore linear in the scale vector s.

Search (bottom-up skyline): at every step the lowest corner of the skyline is
filled with some unplaced block. Whenever the search decides two edges
coincide (a block's right edge meets the segment end, two neighbouring
segment tops merge, a top reaches the canvas ceiling) a linear equation is
added. Equations are kept as an orthogonal basis, so the current best scale
estimate (minimum change from the nominal sizes that satisfies every
equation so far) is updated cheaply and all later geometric decisions use
it. When every block is placed and every segment closes at the ceiling the
scales satisfy all equations exactly and the layout is a perfect tiling.
"""
import math
import time


class _Timeout(Exception):
    pass


def _dot(u, v, n):
    t = 0.0
    for k in range(n):
        t += u[k] * v[k]
    return t


GROW = 1.12


def solve(instance, time_limit, tol_frac=0.03):
    cw = float(instance["canvas"]["width"])
    ch = float(instance["canvas"]["height"])
    area = cw * ch
    B = instance["blocks"]
    n = len(B)
    ids = [b["id"] for b in B]
    a = [math.sqrt(b["target_aspect_ratio"]) for b in B]
    bb = [1.0 / x for x in a]
    smin = [math.sqrt(b["min_area"]) * (1 + 1e-7) for b in B]
    kappa = math.sqrt(area / sum(b["min_area"] for b in B))
    s0 = [x * kappa for x in smin]
    tolm = tol_frac * math.sqrt(area)
    deadline = time.time() + time_limit
    nodes = [0]
    failed = set()

    def const(v):
        f = [0.0] * (n + 1)
        f[n] = v
        return f

    def add(f, g, c=1.0):
        return [x + c * y for x, y in zip(f, g)]

    def ev(f, s):
        t = f[n]
        for k in range(n):
            if f[k]:
                t += f[k] * s[k]
        return t

    # equations: list of (u, t, uu); solution s = s0 + sum u*(t-u.s0)/uu
    def add_eq(eqs, row):
        e = row[:n]
        t = -row[n]
        norm0 = _dot(e, e, n)
        for (u, tt, uu) in eqs:
            d = _dot(e, u, n) / uu
            if d != 0.0:
                e = [x - d * y for x, y in zip(e, u)]
                t -= d * tt
        nn = _dot(e, e, n)
        if nn <= 1e-9 * max(norm0, 1e-12):
            # dependent: must already hold
            return eqs if abs(t) <= 5e-3 else None
        return eqs + [(e, t, nn)]

    def solve_s(eqs):
        s = list(s0)
        for (u, t, uu) in eqs:
            c = (t - _dot(u, s, n)) / uu
            if c != 0.0:
                s = [x + c * y for x, y in zip(s, u)]
        # sequential projection onto orthogonal rows == full projection
        return s

    def feasible(s, slack=0.97, cap=1.01):
        tot = 0.0
        for k in range(n):
            if s[k] < smin[k] * slack or s[k] > smin[k] * GROW:
                return False
            tot += s[k] * s[k]
        return tot <= cap * area

    ew = [[(1.0 if k == i else 0.0) for k in range(n)] + [0.0] for i in range(n)]
    wform = []
    hform = []
    for i in range(n):
        wform.append([a[i] * x for x in ew[i][:n]] + [0.0])
        hform.append([bb[i] * x for x in ew[i][:n]] + [0.0])

    placed = []  # (i, xform, yform)

    def minw_rem(used, s):
        m = 1e18
        for i in range(n):
            if not (used >> i) & 1:
                m = min(m, a[i] * s[i])
        return m

    def widths_reach(rem, s, limit):
        reach = 1
        full = (1 << (int(limit * 4) + 16)) - 1
        for i in rem:
            w = int(a[i] * s[i] * 4)
            reach |= (reach << w) & full
        return reach

    def fillable(reach, R):
        tol = max(2, int(0.05 * R * 4))
        lo = max(0, int(R * 4) - tol)
        return bool((reach >> lo) & ((1 << (2 * tol + 1)) - 1))

    def finalize(eqs, sky):
        # every segment must close at the ceiling
        e2 = eqs
        for seg in sky:
            if not seg[3]:
                row = add(seg[2], const(-ch))
                e2 = add_eq(e2, row)
                if e2 is None:
                    return None
        s = solve_s(e2)
        if not feasible(s, 1 - 1e-9, 1.0 + 1e-6):
            return None
        out = []
        for (i, xf, yf) in placed:
            out.append({"id": ids[i], "x": ev(xf, s), "y": ev(yf, s),
                        "width": a[i] * s[i], "height": bb[i] * s[i]})
        # The targets are rounded, so the exact solution closes only to about
        # 1e-4 units. Shrink every tile slightly about its centre to absorb it.
        eps = 1e-6
        worst = 0.0
        for p in out:
            worst = max(worst, -p["x"], -p["y"], p["x"] + p["width"] - cw,
                        p["y"] + p["height"] - ch)
        for u in range(len(out)):
            for v in range(u + 1, len(out)):
                p, q = out[u], out[v]
                ox = min(p["x"] + p["width"], q["x"] + q["width"]) - max(p["x"], q["x"])
                oy = min(p["y"] + p["height"], q["y"] + q["height"]) - max(p["y"], q["y"])
                if ox > 0 and oy > 0:
                    worst = max(worst, min(ox, oy) / 2.0)
        d = max(worst, 0.0) + 3e-6
        if d > 4e-3:
            return None
        tot = 0.0
        for p in out:
            p["x"] += d
            p["y"] += d
            p["width"] -= 2 * d
            p["height"] -= 2 * d
            tot += p["width"] * p["height"]
        if tot < 0.9995 * area:
            return None
        for k, p in enumerate(out):
            bl = B[ids.index(p["id"])]
            r = p["width"] / p["height"]
            t, tol = bl["target_aspect_ratio"], bl["aspect_tolerance"]
            if r < t * (1 - tol) or r > t * (1 + tol):
                return None
            if p["width"] * p["height"] < bl["min_area"]:
                return None
        return out

    def resolve_closures(sky, eqs, s, cont):
        """Branch over ambiguous ceiling closures / merges, then cont(...)."""
        m = len(sky)
        for j in range(m):
            seg = sky[j]
            if seg[3] or seg[5]:
                continue
            y = ev(seg[2], s)
            if y > ch + tolm:
                return None
            if y >= ch - tolm:
                e2 = add_eq(eqs, add(seg[2], const(-ch)))
                if e2 is not None:
                    s2 = solve_s(e2)
                    if feasible(s2):
                        sky2 = [list(q) for q in sky]
                        sky2[j][3] = True
                        sky2[j][5] = True
                        r = resolve_closures(sky2, e2, s2, cont)
                        if r:
                            return r
                sky2 = [list(q) for q in sky]
                sky2[j][5] = True
                return resolve_closures(sky2, eqs, s, cont)
        for j in range(m - 1):
            A, Bn = sky[j], sky[j + 1]
            if A[3] != Bn[3] or A[4]:
                continue
            ya, yb = ev(A[2], s), ev(Bn[2], s)
            if abs(ya - yb) <= tolm:
                order = ("m", "s") if abs(ya - yb) < 0.3 * tolm else ("s", "m")
                for op in order:
                    if op == "m":
                        e2 = add_eq(eqs, add(A[2], Bn[2], -1.0))
                        if e2 is None:
                            continue
                        s2 = solve_s(e2)
                        if not feasible(s2):
                            continue
                        merged = [A[0], Bn[1], A[2], A[3], Bn[4], A[5] and Bn[5]]
                        r = resolve_closures(sky[:j] + [merged] + sky[j + 2:], e2, s2, cont)
                    else:
                        sky2 = [list(q) for q in sky]
                        sky2[j][4] = True
                        r = resolve_closures(sky2, eqs, s, cont)
                    if r:
                        return r
                return None
        return cont(sky, eqs, s)

    def dfs(used, sky, eqs, s):
        nodes[0] += 1
        if nodes[0] % 64 == 0 and time.time() > deadline:
            raise _Timeout
        if used == (1 << n) - 1:
            return finalize(eqs, sky)
        key = (used, tuple((round(ev(q[0], s) / 3), round(ev(q[1], s) / 3), round(ev(q[2], s) / 3), q[3], q[4], q[5]) for q in sky))
        if key in failed:
            return None
        res_ = dfs_inner(used, sky, eqs, s)
        if not res_:
            failed.add(key)
        return res_

    def dfs_inner(used, sky, eqs, s):
        rem_all = [q for q in range(n) if not (used >> q) & 1]
        reach_all = widths_reach(rem_all, s, cw)
        yv = [ev(seg[2], s) if not seg[3] else ch + 1.0 for seg in sky]
        for j, seg in enumerate(sky):
            if seg[3]:
                continue
            if (j > 0 and yv[j - 1] < yv[j] + 1e-9) or (j + 1 < len(sky) and yv[j + 1] < yv[j] + 1e-9):
                continue
            wj = ev(seg[1], s) - ev(seg[0], s)
            if not fillable(reach_all, wj):
                return None
        ys_ = [(ev(seg[2], s), j) for j, seg in enumerate(sky) if not seg[3]]
        if not ys_:
            return None
        ymin = min(v for v, _ in ys_)
        corners = sorted((v, j) for v, j in ys_ if v <= ymin + 0.5 * tolm)
        for y0, j in corners:
            r = fill_corner(used, sky, eqs, s, y0, j)
            if r:
                return r
        return None

    def fill_corner(used, sky, eqs, s, y0, j):
        seg = sky[j]
        x0 = ev(seg[0], s)
        W = ev(seg[1], s) - x0
        rem = [i for i in range(n) if not (used >> i) & 1]
        mw = min(a[i] * s[i] for i in rem)
        mh = min(bb[i] * s[i] for i in rem)
        if ch - y0 < 0.85 * mh or W < 0.85 * mw:
            return None
        cands = []
        for i in rem:
            w, h = a[i] * s[i], bb[i] * s[i]
            if y0 + h > ch + tolm or w > W + 2 * tolm:
                continue
            cands.append((abs(w - W), i, w))
        cands.sort()
        for _, i, w in cands:
            options = ["snap"]
            if w <= W - 0.85 * mw:
                others = [q for q in rem if q != i]
                if fillable(widths_reach(others, s, W), W - w):
                    options.append("free")
            for op in options:
                e2, s2 = eqs, s
                if op == "snap":
                    e2 = add_eq(eqs, add(add(seg[0], wform[i]), seg[1], -1.0))
                    if e2 is None:
                        continue
                    s2 = solve_s(e2)
                    if not feasible(s2):
                        continue
                if x0 + a[i] * s2[i] > cw + tolm:
                    continue
                nx1 = add(seg[0], wform[i])
                ny = add(seg[2], hform[i])
                new = sky[:j] + [[seg[0], nx1, ny, False, False, False]]
                if op == "free":
                    new.append([nx1, seg[1], seg[2], False, False, False])
                new += sky[j + 1:]
                placed.append((i, seg[0], seg[2]))
                r = resolve_closures(new, e2, s2,
                                     lambda sk, eq, ss, u=used | (1 << i): dfs(u, sk, eq, ss))
                if r:
                    return r
                placed.pop()
        return None


    sky0 = [[const(0.0), const(cw), const(0.0), False, False, False]]
    try:
        return dfs(0, sky0, [], list(s0))
    except _Timeout:
        return None
