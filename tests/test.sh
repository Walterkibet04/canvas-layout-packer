#!/usr/bin/env bash
# Verifier entry point. Runs as root. The submission's code is only ever
# executed as the unprivileged "nobody" user (see harness/lib.py), so it
# cannot write into /logs/verifier or read the tests. The reward is
# written here, after every submission process has been killed.
set -uo pipefail

umask 077
mkdir -p /logs/verifier
chmod 700 /logs/verifier
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json /logs/verifier/ctrf.json

if [ ! -x /app/start.sh ]; then
  echo "FATAL: /app/start.sh missing or not executable" >&2
  echo -n "0" > /logs/verifier/reward.txt
  exit 0
fi

chmod -R a+rX /app
# no setuid/setgid bits and no file capabilities in the submission's tree
find /app -xdev \( -perm -4000 -o -perm -2000 \) -exec chmod u-s,g-s {} + 2>/dev/null || true
if command -v setcap >/dev/null 2>&1; then
  find /app -xdev -type f -exec setcap -r {} + 2>/dev/null || true
fi
chmod -R go-rwx /tests

cd /tests/harness
pytest --ctrf /logs/verifier/ctrf.json -q
RC=$?

# make sure nothing the submission started is still alive before the
# reward is decided
pkill -9 -u nobody 2>/dev/null || true
pkill -9 -U nobody 2>/dev/null || true
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json

if [ "$RC" -eq 0 ]; then
  echo -n "1" > /logs/verifier/reward.txt
else
  echo -n "0" > /logs/verifier/reward.txt
fi

echo "verifier finished with pytest exit code ${RC}"
exit 0
