"""
Dependency Tracker - Cross-process shared state for test case dependency enforcement.

Test cases can declare a 'Dependency' column whose value is the TC ID of a prerequisite.
A test only runs if its dependency passed; otherwise it is skipped (cascading to its own dependents).

State is stored in a small JSON file (path from DEPENDENCY_STATE_FILE env var) that is shared
across all pytest-xdist workers via a file-level spinlock, so parallel execution is safe.
"""

import json
import os
import time

from utils.env_vars import EnvVar


# ── State file helpers ────────────────────────────────────────────────────────

def _get_state_file() -> str:
    return os.environ.get(EnvVar.DEPENDENCY_STATE_FILE, '')


def _acquire_lock(lock_path: str, timeout: float = 10.0) -> bool:
    """Spin-lock implemented via exclusive file creation. Returns True if acquired."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except (FileExistsError, OSError):
            time.sleep(0.05)
    return False


def _release_lock(lock_path: str) -> None:
    try:
        os.remove(lock_path)
    except OSError:
        pass


def _read_state(state_file: str) -> dict:
    lock_path = state_file + '.lock'
    if not _acquire_lock(lock_path):
        return {}
    try:
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                return json.load(f)
        return {}
    except (OSError, json.JSONDecodeError):
        return {}
    finally:
        _release_lock(lock_path)


def _write_state(state_file: str, tc_id_val: str, result: str) -> None:
    lock_path = state_file + '.lock'
    if not _acquire_lock(lock_path, timeout=15.0):
        return
    try:
        state = {}
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                try:
                    state = json.load(f)
                except (OSError, json.JSONDecodeError):
                    state = {}
        state[tc_id_val] = result
        tmp_path = state_file + '.tmp'
        with open(tmp_path, 'w') as f:
            json.dump(state, f)
        os.replace(tmp_path, state_file)
    except OSError:
        pass
    finally:
        _release_lock(lock_path)


# ── Public API ────────────────────────────────────────────────────────────────

def record_extracted_variables(tc_id_val: str, variables: dict) -> None:
    """
    Store variables extracted from a test case's response so dependents can use them.
    Must be called BEFORE record_result so dependents always find the variables available
    as soon as they are unblocked by the 'passed' result.
    No-op when DEPENDENCY_STATE_FILE is not set.
    """
    state_file = _get_state_file()
    if not state_file:
        return
    lock_path = state_file + '.lock'
    if not _acquire_lock(lock_path, timeout=15.0):
        return
    try:
        state = {}
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                try:
                    state = json.load(f)
                except (OSError, json.JSONDecodeError):
                    state = {}
        state.setdefault('_vars', {})[tc_id_val] = variables
        tmp_path = state_file + '.tmp'
        with open(tmp_path, 'w') as f:
            json.dump(state, f)
        os.replace(tmp_path, state_file)
    except OSError:
        pass
    finally:
        _release_lock(lock_path)


def get_extracted_variables(dep_tc_id: str) -> dict:
    """
    Return the variables that were extracted from a dependency test case's response.
    Returns an empty dict when no variables were stored or state file is not set.
    """
    state_file = _get_state_file()
    if not state_file:
        return {}
    state = _read_state(state_file)
    return state.get('_vars', {}).get(dep_tc_id, {})


def record_result(tc_id_val: str, result: str) -> None:
    """
    Record the outcome of a test case.
    result must be one of: 'passed', 'failed', 'skipped'.
    No-op when DEPENDENCY_STATE_FILE is not set.
    """
    state_file = _get_state_file()
    if not state_file:
        return
    _write_state(state_file, tc_id_val, result)


def check_dependency(dep_tc_id: str, timeout: int = 300) -> str:
    """
    Block until the dependency test case has recorded a result or the timeout expires.

    Returns one of:
        'passed'  – dependency passed, proceed with the test
        'failed'  – dependency failed, skip the dependent test
        'skipped' – dependency was skipped (its own dependency failed), skip too
        'timeout' – dependency never recorded a result within `timeout` seconds

    If DEPENDENCY_STATE_FILE is not set, returns 'passed' immediately (no enforcement).
    """
    state_file = _get_state_file()
    if not state_file:
        return 'passed'

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = _read_state(state_file)
        if dep_tc_id in state:
            return state[dep_tc_id]
        time.sleep(1)

    return 'timeout'


# ── Topological sort ──────────────────────────────────────────────────────────

def topological_sort(test_cases: list, tc_id_col: str, tc_dep_col: str) -> list:
    """
    Re-order test cases so every dependency comes before its dependents.

    Dependencies that point outside the current test set (not being run) are ignored
    for ordering purposes; they are handled at runtime via check_dependency / _dep_in_run.

    Circular dependencies are detected and the involved cases are appended at the end
    with a printed warning.
    """
    tc_map = {}
    for tc in test_cases:
        tid = str(tc.get(tc_id_col, '')).strip()
        if tid:
            tc_map[tid] = tc

    in_degree = {tid: 0 for tid in tc_map}
    dependents: dict[str, list] = {tid: [] for tid in tc_map}

    for tid in tc_map:
        dep = str(tc_map[tid].get(tc_dep_col, '')).strip()
        if dep and dep in in_degree:
            in_degree[tid] += 1
            dependents[dep].append(tid)

    # Kahn's BFS topological sort – stable (sorted) within each level
    queue = sorted(tid for tid, deg in in_degree.items() if deg == 0)
    sorted_ids = []

    while queue:
        node = queue.pop(0)
        sorted_ids.append(node)
        for child in sorted(dependents[node]):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    # Any node still with in_degree > 0 is part of a cycle
    cycle_nodes = [tid for tid, deg in in_degree.items() if deg > 0]
    if cycle_nodes:
        print(f"WARNING: Dependency cycle detected involving test cases: {cycle_nodes}. "
              f"They will be executed in their original order.")
        sorted_ids.extend(sorted(cycle_nodes))

    sorted_tcs = [tc_map[tid] for tid in sorted_ids if tid in tc_map]

    # Preserve any rows that had no usable TC ID (shouldn't happen but be safe)
    seen = set(sorted_ids)
    for tc in test_cases:
        tid = str(tc.get(tc_id_col, '')).strip()
        if not tid or tid not in seen:
            sorted_tcs.append(tc)

    return sorted_tcs
