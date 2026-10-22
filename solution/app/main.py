#!/usr/bin/env python3
import json
import os
import sys

from floorplan_solver import solve


def main():
    if len(sys.argv) < 2:
        print("usage: main.py <instance.json>", file=sys.stderr)
        return 2
    with open(sys.argv[1], "r") as f:
        instance = json.load(f)
    limit = float(os.environ.get("TIME_LIMIT_SECONDS", "60"))
    placements = solve(instance, limit * 0.8)
    print(json.dumps({"placements": placements or []}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
