#!/usr/bin/env bash
set -euo pipefail
SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/app"
rm -rf /app
mkdir -p /app
cp "$SOLUTION_DIR/main.py" "$SOLUTION_DIR/floorplan_solver.py" /app/
cp "$SOLUTION_DIR/start.sh" /app/start.sh
chmod +x /app/start.sh
echo "built self-contained artifact at /app"
