"""Decision 002-B corrected run. Same as inside_run.py except step 4: CodeGraph extraction is NOT rerun.
The two index copies (copyA, copyB) and their index logs are reused read-only from run REUSE (t002-20261021T1049-3);
the real index is read immutable as before. Adapter, CTs, checker and validation x2 run fresh with the Decision 002-B code.
Usage: inside_run_002b.py <run_dir>"""
import json, os, shutil, sqlite3, subprocess, sys, time
T = "/workspace/traces-research/task002"; SRC = f"{T}/src/fsft"; SHA = "b1125d8839482cb7bbae603ddc6d0081bf87532e"
PY = f"{T}/tools/py314/bin/python"; NODE = "/usr/bin/node"; TSM = f"{T}/tools/ts6/node_modules/typescript"
sys.path.insert(0, f"{T}/adapter")
from common import canonical_hash, now_ist

RUN = os.path.abspath(sys.argv[1]); RID = os.path.basename(RUN)
LOG = open(os.path.join(RUN, "commands.log"), "a")
REUSE = f"{T}/work/t002-20261021T1049-3"


def sh(cmd, cwd=None, env=None, check=False, out=None):
    t0 = time.time()
    p = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True)
    LOG.write(f"\n[{now_ist()}] $ {' '.join(cmd)}{'  (cwd ' + cwd + ')' if cwd else ''}\n{p.stdout[-6000:]}{p.stderr[-6000:]}[exit={p.returncode} wall_s={time.time() - t0:.1f}]\n"); LOG.flush()
    if out:
        open(out, "w").write(p.stdout)
    if check and p.returncode != 0:
        raise SystemExit(f"command failed: {cmd}: {p.stderr[-2000:]}")
    return p


def manifest(name, checkout, index, extra=None, cg=None):
    d = os.path.join(RUN, name); os.makedirs(d, exist_ok=True)
    m = {"run_id": RID, "repo": "fastapi/full-stack-fastapi-template", "repo_sha": SHA, "checkout_path": checkout, "index_path": index,
         "codegraph": {"package": "@colbymchenry/codegraph", "version": "1.6.2", "npm_integrity": "sha512-hODH/mGnCf3IUMs6rzktv/zbecJIKJfdZAYHZ9mqecb0G7ZkHaA8CZafDVnswANFEL1YFcG+lfAwc5SIXzUH6Q==",
                       "npm_shasum": "372b7b4f0190197b07d444116d6692240883a2d5", "schema_version_max": 11, "extraction_version": "27"},
         "wrapper": {"path": f"{T}/tools/offline.sh", "sha256": "81042fecf68704913ba73359291e9b658f481e1d1853065fd7b845b0cb9d6466"},
         "env": {"telemetry_disabled": True, "isolation": "unshare -rn (tools/offline.sh)", "netprobe_log": os.path.join(RUN, "netprobe.log")},
         "adapter_out": os.path.join(d, "out"), "package_dir": f"{T}/tools/node_modules/@colbymchenry/codegraph", "lockfile": f"{T}/tools/package-lock.json",
         "registry_record_log": f"{T}/logs/setup_npm.log"}
    if cg:
        m["codegraph"].update(cg)
    if extra:
        m.update(extra)
    p = os.path.join(d, "manifest.json"); json.dump(m, open(p, "w"), indent=1)
    return p, m


def adapter(name, checkout, index, **kw):
    p, m = manifest(name, checkout, index, **kw)
    r = sh([PY, f"{T}/adapter/cg_adapter.py", "--manifest", p])
    e = os.path.join(m["adapter_out"], "errors.json")
    return {"exit": r.returncode, "stdout": r.stdout.strip(), "errors": json.load(open(e)) if os.path.exists(e) else None, "out": m["adapter_out"], "manifest": p}


def clone(name, rev=SHA):
    d = os.path.join(RUN, name)
    sh(["git", "clone", "-q", "--no-hardlinks", "--no-checkout", SRC, d], check=True)
    sh(["git", "-C", d, "-c", "advice.detachedHead=false", "checkout", "-q", "--detach", rev], check=True)
    return d


def db_copy(name, mutate):
    d = os.path.join(RUN, "ct", name); os.makedirs(d, exist_ok=True); p = os.path.join(d, "codegraph.db")
    src = sqlite3.connect(f"file:{SRC}/.codegraph/codegraph.db?mode=ro&immutable=1", uri=True); dst = sqlite3.connect(p); src.backup(dst); src.close()
    mutate(dst); dst.commit(); dst.close()
    return p


def main():
    res = {"run_id": RID, "started": now_ist()}
    # ---- step 5 injected set (validator inputs only) ----
    vi = os.path.join(RUN, "validator_inputs"); os.makedirs(vi, exist_ok=True)
    sh([PY, f"{T}/fixtures/build_fixture.py", "--fixture-out", f"{T}/fixtures/chain_create_item.json", "--injected-out", f"{vi}/injected.jsonl", "--run-id", RID, "--spotcheck-out", f"{RUN}/fixture_spotcheck.txt"], check=True)
    # ---- step 4 indexing: NOT rerun (Decision 002-B: reuse run REUSE raw output). Index copies are read-only inputs. ----
    prev = json.load(open(os.path.join(REUSE, "inside_result.json")))
    idx = {}
    for c in ("copyA", "copyB"):
        d = os.path.join(REUSE, c)
        idx[c] = {"exit": prev["index_runs"][c]["exit"], "dir": d, "reused_from": os.path.basename(REUSE), "index_log": os.path.join(REUSE, f"index_{c}.log"),
                  "index_db_sha256": sh(["sha256sum", os.path.join(d, ".codegraph/codegraph.db")]).stdout.split()[0]}
        sh(["git", "-C", d, "status", "--porcelain"], env={"GIT_OPTIONAL_LOCKS": "0"})
    res["index_runs"] = idx
    shutil.copyfile(os.path.join(REUSE, "netprobe.log"), os.path.join(RUN, "netprobe_index_reused.log"))
    # ---- adapter: real index + copies ----
    real_db = f"{SRC}/.codegraph/codegraph.db"
    A = {"real": adapter("adapter_real", SRC, real_db)}
    for c in ("copyA", "copyB"):
        A[c] = adapter(f"adapter_{c}", idx[c]["dir"], os.path.join(idx[c]["dir"], ".codegraph/codegraph.db"))
    res["adapter"] = A
    if A["real"]["exit"] != 0:
        json.dump(res, open(os.path.join(RUN, "inside_result.json"), "w"), indent=1); raise SystemExit("adapter failed on the real index")
    rec_real = os.path.join(A["real"]["out"], "records.jsonl")
    res["canonical_hash"] = {k: (canonical_hash([json.loads(l) for l in open(os.path.join(v["out"], "records.jsonl"))]) if v["exit"] == 0 else None) for k, v in A.items()}
    # ---- CT5 schema ----
    sh([PY, f"{T}/validators/schema_check.py", f"{T}/spec/evidence_record.schema.json", "--self-test"], out=os.path.join(RUN, "schema_selftest.txt"))  # fixed: 1049-3 omitted the schema path
    sh([PY, f"{T}/validators/schema_check.py", f"{T}/spec/evidence_record.schema.json", rec_real], out=os.path.join(RUN, "schema_adapter.json"))
    # ---- negative contract tests on copies ----
    cA = idx["copyA"]["dir"]; dbA = os.path.join(cA, ".codegraph/codegraph.db")
    neg = {}
    neg["CT1a_version_1.6.3"] = adapter("ct/CT1a", cA, db_copy("CT1a", lambda c: c.execute("UPDATE project_metadata SET value='1.6.3' WHERE key='indexed_with_version'")))
    neg["CT1b_wrong_integrity"] = adapter("ct/CT1b", cA, dbA, cg={"npm_integrity": "sha512-" + "A" * 86 + "=="})
    neg["CT2a_edges_provenance_renamed"] = adapter("ct/CT2a", cA, db_copy("CT2a", lambda c: c.execute("ALTER TABLE edges RENAME COLUMN provenance TO provenance_x")))
    neg["CT2b_no_unresolved_refs"] = adapter("ct/CT2b", cA, db_copy("CT2b", lambda c: c.execute("DROP TABLE unresolved_refs")))
    c3a = clone("ct/CT3a_clone")
    f3 = os.path.join(c3a, "backend/app/api/routes/items.py"); b = open(f3, "rb").read(); open(f3, "wb").write(b.replace(b"def create_item(", b"def create_iten(", 1))
    neg["CT3a_byte_changed"] = adapter("ct/CT3a", c3a, dbA)
    neg["CT3b_head_minus_1"] = adapter("ct/CT3b", clone("ct/CT3b_clone", SHA + "~1"), dbA)
    neg["CT3c_manifest_other_sha"] = adapter("ct/CT3c", cA, dbA, extra={"repo_sha": "0" * 40})
    def guess(c):
        rid = c.execute("SELECT id FROM edges WHERE json_extract(metadata,'$.resolvedBy')='exact-match' ORDER BY id LIMIT 1").fetchone()[0]
        md = json.loads(c.execute("SELECT metadata FROM edges WHERE id=?", (rid,)).fetchone()[0]); md["resolvedBy"] = "guess"
        c.execute("UPDATE edges SET metadata=? WHERE id=?", (json.dumps(md), rid))
    neg["CT4_resolvedBy_guess"] = adapter("ct/CT4", cA, db_copy("CT4", guess))
    neg["CT9a_absolute_path"] = adapter("ct/CT9a", cA, db_copy("CT9a", lambda c: c.execute("UPDATE files SET path='/etc/passwd' WHERE path='backend/app/crud.py'")))
    neg["CT9b_dotdot_path"] = adapter("ct/CT9b", cA, db_copy("CT9b", lambda c: c.execute("UPDATE files SET path='../outside.py' WHERE path='backend/app/crud.py'")))
    res["negative"] = neg
    # ---- frozen checker (CT7) ----
    ck = f"{T}/checker"
    sh(["sha256sum", "-c", "SHA256SUMS"], cwd=ck, out=os.path.join(RUN, "checker_sha256.txt"))
    for mode in ("parser", "lab_route"):
        sh([PY, f"{ck}/line_checker_v1.py", "--db", real_db, "--src", SRC, "--sha", SHA, "--ts-module", TSM, "--mode", mode, "--out", os.path.join(RUN, f"checker_{mode}.json")], out=os.path.join(RUN, f"checker_{mode}_stdout.json"))
    sh([PY, f"{T}/step1/verbatim_check_lines_immutable.py"], out=os.path.join(RUN, "check_lines_verbatim.txt"))
    # ---- steps 7 to 9 validation, twice (determinism), measured ----
    vt = {}
    for k in ("v1", "v2"):
        vd = os.path.join(RUN, k); os.makedirs(vd, exist_ok=True)
        json.dump({"run_id": RID}, open(os.path.join(vd, "manifest.json"), "w"))
        cmd = f"{PY} {T}/validators/run_validation.py --run-dir {vd} --records {rec_real} --fixture {T}/fixtures/chain_create_item.json --injected {vi}/injected.jsonl"
        r = sh([PY, "/workspace/traces-research/_tests/measure.py", cmd])
        vt[k] = {"exit": r.returncode, "measure": [l for l in r.stdout.splitlines() if l.startswith("MEASURE")], "stdout": r.stdout[-3000:], "stderr": r.stderr[-3000:]}
        if r.returncode == 0:
            ev = [json.loads(l) for l in open(os.path.join(vd, "validation", "evidence.jsonl"))]
            vt[k]["canonical_hash"] = canonical_hash(ev)
            sh([PY, f"{T}/validators/schema_check.py", f"{T}/spec/evidence_record.schema.json", os.path.join(vd, "validation", "evidence.jsonl")], out=os.path.join(vd, "schema_evidence.json"))
            sh([PY, f"{T}/pipeline/report.py", RUN, os.path.join(vd, "validation")], check=True)
    res["validation"] = vt
    res["finished"] = now_ist()
    json.dump(res, open(os.path.join(RUN, "inside_result.json"), "w"), indent=1, default=str)
    print("INSIDE_DONE", json.dumps({k: v["exit"] for k, v in vt.items()}))
    if any(v["exit"] != 0 for v in vt.values()):
        raise SystemExit("validation failed")


main()
