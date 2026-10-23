"""No unintended outbound calls (charter s5, s7).

Worker: during a real index job the only network-capable step may be the clone of the target URL. Every analysis
process runs through workers/sandbox.sh (unshare -rn), and the in-sandbox probes must show the network denied.
App: every read endpoint, explain and the chat bundle make no socket connection off the loopback and spawn no
network-capable git. Two layers: an audit hook over this Python process, and an OS-level run of `traces serve`
inside a fresh network namespace that holds only loopback."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from .conftest import Indexed, monitor_outbound

NET_GIT = {"clone", "fetch", "ls-remote", "pull", "push", "submodule", "remote", "archive"}


def _git_sub(argv: list[str]) -> str | None:
    if not argv or Path(argv[0]).name != "git":
        return None
    skip_next = False
    for a in argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if a in ("-c", "-C"):
            skip_next = True
            continue
        if a.startswith("-"):
            continue
        return a
    return None


def test_worker_only_fetches_the_target(indexed_hostile: Indexed):
    ob = indexed_hostile.outbound
    assert ob.non_local_connects() == [], ob.non_local_connects()
    net = [a for a in ob.spawns if _git_sub(a) in NET_GIT]
    cache_src = str(indexed_hostile.cache_dir / "targets" / indexed_hostile.repo_id / indexed_hostile.sha / "source")
    target = [a for a in net if indexed_hostile.ref.clone_url in a]
    local = [a for a in net if cache_src in a and indexed_hostile.ref.clone_url not in a]
    assert len(target) == 1 and _git_sub(target[0]) == "clone", net
    # the throwaway working copy is a clone of the pinned cache checkout (a local path), nothing else
    assert all(_git_sub(a) == "clone" for a in local) and len(local) == 1, net
    assert len(net) == len(target) + len(local), net
    for a in ob.spawns:
        name = Path(a[0]).name if a else ""
        if name == "git":
            continue
        assert name == "bash" and a[1].endswith("workers/sandbox.sh"), f"analysis process outside the sandbox: {a[:4]}"


def test_worker_sandbox_probes_show_network_denied(indexed_hostile: Indexed):
    run = indexed_hostile.data_dir / "runs" / "idx-sec"
    probe = (run / "netprobe.log").read_text()
    assert "state DOWN" in probe and "Could not resolve host: registry.npmjs.org" in probe
    assert "Failed to connect to 1.1.1.1" in probe or "Network is unreachable" in probe
    assert "http_code=200" not in probe
    idx = (run / "netprobe_index.log").read_text()
    outer = os.readlink("/proc/self/ns/net")
    assert outer not in idx, "an indexer process ran in the host network namespace"


def _exercise(client, ix: Indexed) -> list[int]:
    b = f"/api/v1/repos/{ix.repo_id}/snapshots/{ix.sha}"
    gets = ["/api/v1/health", "/api/v1/meta", "/api/v1/repos", f"/api/v1/repos/{ix.repo_id}", f"/api/v1/repos/{ix.repo_id}/snapshots",
            b, f"{b}/claims", f"{b}/overview", f"{b}/components", f"{b}/routes", f"{b}/graph", f"{b}/source?path=app/main.py",
            f"{b}/trace?from=app/main.py::run", f"{b}/history/timeline", f"{b}/history/hotspots", f"{b}/history/cochange",
            f"{b}/history/milestones", f"{b}/history/rationale", f"{b}/history/lifecycle?path=app/main.py", f"{b}/export",
            f"/api/v1/repos/{ix.repo_id}/compare?base={ix.sha}&head={ix.sha}", "/api/v1/jobs/sec"]
    codes = [client.get(u).status_code for u in gets]
    codes.append(client.post(f"{b}/explain", json={"question": "What does app/main.py call?"}).status_code)
    codes.append(client.post(f"{b}/chat/bundle", json={"question": "What does app/main.py call?"}).status_code)
    return codes


def test_app_read_paths_make_no_outbound_calls(indexed_hostile: Indexed, hostile_client):
    with monitor_outbound() as ob:
        codes = _exercise(hostile_client, indexed_hostile)
    assert all(c < 500 for c in codes), codes
    assert codes.count(200) >= len(codes) - 2, codes
    assert ob.non_local_connects() == []
    assert [a for a in ob.spawns if _git_sub(a) in NET_GIT] == []


SERVE_IN_NETNS = textwrap.dedent("""
    set -u
    ip link set lo up
    "$PY" -m traces.cli serve --host 127.0.0.1 --port 18765 > "$OUT/serve.log" 2>&1 &
    pid=$!
    for _ in $(seq 1 100); do curl -fsS http://127.0.0.1:18765/api/v1/health >/dev/null 2>&1 && break; sleep 0.1; done
    B="http://127.0.0.1:18765/api/v1/repos/$RID/snapshots/$SHA"
    for u in /api/v1/health /api/v1/meta /api/v1/repos; do curl -s -o /dev/null -w "%{http_code} $u\\n" "http://127.0.0.1:18765$u"; done
    for u in overview graph components routes claims "source?path=app/main.py" history/timeline history/hotspots; do
      curl -s -o /dev/null -w "%{http_code} $u\\n" "$B/$u"; done
    curl -s -o /dev/null -w "%{http_code} explain\\n" -H 'content-type: application/json' -d '{"question":"what calls helper?"}' "$B/explain"
    echo "netns $(readlink /proc/self/ns/net)"
    curl -sS -m 5 -o /dev/null https://registry.npmjs.org/ 2>&1 | head -1
    kill $pid; wait $pid 2>/dev/null
""")


def test_app_serves_inside_an_empty_network_namespace(indexed_hostile: Indexed, tmp_path):
    if not shutil.which("ip") or not shutil.which("curl"):
        pytest.skip("needs ip and curl")
    if subprocess.run(["unshare", "-rn", "true"], capture_output=True).returncode != 0:
        pytest.skip("unshare -rn not available")
    env = {**os.environ, "PY": sys.executable, "OUT": str(tmp_path), "RID": indexed_hostile.repo_id, "SHA": indexed_hostile.sha,
           "TRACES_DATA_DIR": str(indexed_hostile.data_dir), "TRACES_CACHE_DIR": str(indexed_hostile.cache_dir)}
    p = subprocess.run(["unshare", "-rn", "bash", "-c", SERVE_IN_NETNS], env=env, capture_output=True, text=True, timeout=120)
    out = p.stdout + p.stderr
    (Path(os.environ.get("TRACES_ACCEPTANCE_DIR", tmp_path)) / "netns_serve.txt").write_text(out) if os.environ.get("TRACES_ACCEPTANCE_DIR") else None
    lines = [ln for ln in out.splitlines() if ln[:3].isdigit()]
    assert len(lines) == 12, out
    assert all(ln.startswith("200 ") for ln in lines), out
    assert os.readlink("/proc/self/ns/net") not in out
    assert "Could not resolve host" in out
