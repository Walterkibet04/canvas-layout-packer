import json
import os
import signal
import subprocess
import tempfile

from verify import verify_placement

APP_DIR = "/app"
UNPRIVILEGED_USER = "nobody"
UNPRIVILEGED_UID = 65534


def _proc_uids(entry):
    """Real, effective, saved and filesystem uids of a process, or None."""
    try:
        with open(f"/proc/{entry}/status") as f:
            for line in f:
                if line.startswith("Uid:"):
                    return [int(x) for x in line.split()[1:5]]
    except (OSError, ValueError):
        pass
    return None


def _proc_session(entry):
    try:
        with open(f"/proc/{entry}/stat") as f:
            data = f.read()
        # the command name is in parentheses and may contain spaces
        rest = data[data.rindex(")") + 2:].split()
        return int(rest[3])  # session id
    except (OSError, ValueError, IndexError):
        return None


def kill_unprivileged_processes(session_id=None):
    """Kill everything the submission could still have running: any process
    with the unprivileged uid in any of its uid fields, and anything left in
    the session the solver was started in (even if it somehow changed uid)."""
    if os.geteuid() != 0:
        return
    me = os.getpid()
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or int(entry) == me:
            continue
        uids = _proc_uids(entry)
        hit = uids is not None and UNPRIVILEGED_UID in uids
        if not hit and session_id is not None:
            hit = _proc_session(entry) == session_id
        if hit:
            try:
                os.kill(int(entry), signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass


def _no_new_privs():
    """Runs in the child after the uid drop: from here on no exec can gain
    privileges, so a setuid binary or file capability shipped in /app is inert."""
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        os._exit(126)


def run_solver(instance, time_limit_seconds, hard_kill_extra=15):
    workdir = tempfile.mkdtemp(prefix="inst-")
    os.chmod(workdir, 0o755)
    path = os.path.join(workdir, "instance.json")
    with open(path, "w") as f:
        json.dump(instance, f)
    os.chmod(path, 0o644)

    # minimal environment: the submission gets its time budget and nothing
    # else from the verifier's own environment
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": "/tmp",
        "TIME_LIMIT_SECONDS": str(time_limit_seconds),
    }
    kwargs = {}
    if os.geteuid() == 0:
        kwargs.update(user=UNPRIVILEGED_USER, group="nogroup")

    proc = subprocess.Popen(
        [f"{APP_DIR}/start.sh", path],
        env=env, cwd=APP_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
        preexec_fn=_no_new_privs if os.geteuid() == 0 else None, **kwargs,
    )
    try:
        stdout, stderr = proc.communicate(timeout=time_limit_seconds + hard_kill_extra)
        status = "ok"
    except subprocess.TimeoutExpired:
        stdout, stderr, status = "", "", "timeout"
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait()
        kill_unprivileged_processes(session_id=proc.pid)
        try:
            os.remove(path)
            os.rmdir(workdir)
        except OSError:
            pass

    if status != "ok":
        return None, status, ""
    try:
        def _reject_constant(name):
            raise ValueError(f"non-standard JSON constant {name}")

        return (
            json.loads(stdout, parse_constant=_reject_constant).get("placements", []),
            "ok",
            stderr,
        )
    except (json.JSONDecodeError, AttributeError, ValueError):
        return None, "unparseable stdout", stderr


def check(instance, time_limit_seconds):
    placements, status, stderr = run_solver(instance, time_limit_seconds)
    assert placements is not None, f"solver output problem: {status} (stderr: {stderr[:500]})"
    ok, reason, coverage = verify_placement(instance, placements)
    assert ok, f"invalid or insufficient layout: {reason} (coverage={coverage:.4f})"
    return coverage
