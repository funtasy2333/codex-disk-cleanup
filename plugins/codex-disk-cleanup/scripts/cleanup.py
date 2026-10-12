#!/usr/bin/env python3
"""Codex disk cleanup. Python standard library only; no shell execution."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import stat
import sys
import time
import uuid

VERSION = "0.1.4"
RETENTION = {"test": 0, "temp": 7 * 86400, "cron-output": 14 * 86400}
PROTECTED = {".git", ".codex", ".agents", "sessions", "archived_sessions", "memories",
             "skills", "plugins", "outputs", "deliverables", "node_modules", ".ssh",
             ".quarantine", ".codex-disk-cleanup-quarantine"}
SECRETS = {"auth.json", "config.toml", "config.json", "history.jsonl", "AGENTS.md", ".env"}
MAX_BYTES = 64 * 1024 * 1024
MAX_ITEMS = 2000
LEASE = 86400
PLAN_TTL = 900


class Refused(ValueError):
    pass


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def safe_components(path: Path):
    """Reject links, junctions and Git trees, including enclosing repositories."""
    for p in (path, *path.parents):
        try:
            s = p.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(s.st_mode) or getattr(s, "st_file_attributes", 0) & 0x400:
            raise Refused("symlink or reparse point")
        if p.is_dir() and os.path.lexists(p / ".git"):
            raise Refused("Git worktree is protected")


def fingerprint(path: Path):
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
        raise Refused("not a single-link regular file")
    if s.st_size > MAX_BYTES:
        raise Refused("file exceeds 64 MiB limit")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if (before.st_dev, before.st_ino) != (s.st_dev, s.st_ino):
            raise Refused("file changed during open")
        digest = hashlib.sha256()
        with os.fdopen(fd, "rb", closefd=False) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise Refused("file changed during hashing")
        return {"dev": s.st_dev, "ino": s.st_ino, "size": s.st_size,
                "mtime": s.st_mtime_ns, "ctime": s.st_ctime_ns, "mode": s.st_mode,
                "sha256": digest.hexdigest()}
    finally:
        os.close(fd)


def same_content(a, b):
    return all(a[k] == b[k] for k in ("dev", "ino", "size", "mtime", "sha256"))


class Store:
    def __init__(self, data: Path, *, read_only=False):
        # Resolve OS aliases (e.g. /tmp on macOS) once; descendants stay lexical.
        self.data = data.expanduser().resolve()
        if not read_only:
            self.data.mkdir(parents=True, exist_ok=True, mode=0o700)
        safe_components(self.data)
        if self.data == Path.home().resolve() or self.data == Path(self.data.anchor):
            raise Refused("unsafe data directory")
        self.scratch = self.data / "scratch"
        if not read_only:
            self.scratch.mkdir(exist_ok=True, mode=0o700)
        safe_components(self.scratch)
        for name in ("state.sqlite3", "config.json"):
            if os.path.lexists(self.data / name):
                s = (self.data / name).lstat()
                if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
                    raise Refused("unsafe state/config file")
        config_path = self.data / "config.json"
        if config_path.exists():
            self.config = json.loads(config_path.read_text(encoding="utf-8"))
        else:
            self.config = {"schema": 1, "auto": "preview", "maintenance": []}
        if not isinstance(self.config, dict) or self.config.get("schema") != 1:
            raise Refused("invalid config schema")
        if self.config.get("auto") not in ("preview", "quarantine"):
            raise Refused("auto must be preview or quarantine")
        if not isinstance(self.config.get("maintenance"), list):
            raise Refused("invalid maintenance roots")
        self.roots = [self.validate_root(spec) for spec in self.config["maintenance"]]
        specs = self.config.get("project_scratch", [])
        if not isinstance(specs, list) or len(specs) > 16:
            raise Refused("project_scratch must be a list of at most 16 enrolled roots")
        self.project_roots, self.project_errors = [], []
        for spec in specs:
            try:
                valid = self.validate_project_root(spec)
                if any(Path(valid["path"]).is_relative_to(Path(s["path"])) or
                       Path(s["path"]).is_relative_to(Path(valid["path"])) for s in self.project_roots):
                    raise Refused("overlapping project scratch roots")
                self.project_roots.append(valid)
            except (ValueError, OSError) as e:
                self.project_errors.append({"path": spec.get("path") if isinstance(spec, dict) else None,
                                            "reason": str(e)})
        self.db = None
        db_path = self.data / "state.sqlite3"
        if read_only and not db_path.exists():
            return
        if read_only:
            self.db = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True,
                                      timeout=3, isolation_level=None)
        else:
            self.db = sqlite3.connect(db_path, timeout=3, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        if read_only:
            try:
                self.db.execute("PRAGMA query_only=ON")
                row = self.db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
                if not row or row[0] != "1":
                    raise Refused("unsupported state schema")
            except BaseException:
                self.db.close()
                raise
            return
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, seen REAL, ended INTEGER);
        CREATE TABLE IF NOT EXISTS pending (session TEXT, call TEXT, created REAL, paths TEXT,
            PRIMARY KEY(session, call));
        CREATE TABLE IF NOT EXISTS tracked (path TEXT PRIMARY KEY, session TEXT, turn TEXT,
            category TEXT, created REAL, fp TEXT);
        CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY, created REAL, items TEXT, used INTEGER);
        CREATE TABLE IF NOT EXISTS moves (id TEXT PRIMARY KEY, source TEXT, dest TEXT, root TEXT,
            fp TEXT, state TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, at REAL, action TEXT, detail TEXT);
        """)
        row = self.db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
        if row and row[0] != "1":
            self.db.close()
            raise Refused("unsupported state schema")
        self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('schema','1')")

    def close(self):
        if self.db:
            self.db.close()

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def audit(self, action, detail):
        self.db.execute("INSERT INTO audit(at,action,detail) VALUES (?,?,?)",
                        (time.time(), action, compact(detail)))
        # Bound retained audit rows; state never grows with every ignored tool.
        self.db.execute("DELETE FROM audit WHERE id <= (SELECT MAX(id)-10000 FROM audit)")

    def validate_root(self, spec):
        if not isinstance(spec, dict) or spec.get("kind") not in ("cache", "logs"):
            raise Refused("maintenance kind must be cache or logs")
        raw = spec.get("path")
        if not isinstance(raw, str) or not Path(raw).is_absolute():
            raise Refused("maintenance roots must be absolute")
        path = Path(raw)
        safe_components(path)
        path = path.resolve(strict=True)
        codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).resolve()
        permitted = codex_home / spec["kind"]
        if not path.is_relative_to(permitted) or not path.is_dir():
            raise Refused("maintenance root must be within CODEX_HOME/cache or CODEX_HOME/logs")
        if path.is_relative_to(self.data) or self.data.is_relative_to(path):
            raise Refused("maintenance and plugin data overlap")
        days = spec.get("days", 30)
        if type(days) is not int or not 1 <= days <= 3650:
            raise Refused("retention must be 1..3650 days")
        return {"path": str(path), "kind": spec["kind"], "days": days}

    def save_config(self):
        tmp = self.data / (".config-" + uuid.uuid4().hex)
        try:
            with tmp.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(self.config, indent=2) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.data / "config.json")
        finally:
            tmp.unlink(missing_ok=True)

    def validate_project_root(self, spec, *, capture_identity=False):
        if not isinstance(spec, dict):
            raise Refused("project scratch policy must be an object")
        for key in ("path", "project", "session"):
            if not isinstance(spec.get(key), str) or not spec[key]:
                raise Refused("project scratch requires path, project and session")
        if len(spec["session"]) > 512:
            raise Refused("valid session id required")
        if not Path(spec["path"]).is_absolute() or not Path(spec["project"]).is_absolute():
            raise Refused("project and scratch paths must be absolute")
        safe_components(Path(spec["path"]))
        safe_components(Path(spec["project"]))
        root = Path(spec["path"]).resolve(strict=True)
        project = Path(spec["project"]).resolve(strict=True)
        if not root.is_dir() or not project.is_dir() or root == project or not root.is_relative_to(project):
            raise Refused("scratch must be an existing strict subdirectory of the project")
        home = Path.home().resolve()
        codex_home = Path(os.environ.get("CODEX_HOME", str(home / ".codex"))).resolve()
        if project in (home, Path(project.anchor)) or root.is_relative_to(codex_home):
            raise Refused("home and Codex data are protected")
        sensitive = {".ssh", ".codex", ".agents", "sessions", "archived_sessions",
                     "memories", "skills", "plugins"}
        if any(p in sensitive for p in project.parts):
            raise Refused("sensitive project ancestor is protected")
        if root.is_relative_to(self.data) or self.data.is_relative_to(root):
            raise Refused("project scratch and plugin data overlap")
        if any(p in PROTECTED or p in SECRETS or p.startswith(".env") for p in root.relative_to(project).parts):
            raise Refused("protected project path")
        days = spec.get("days", 7)
        if type(days) is not int or not 0 <= days <= 3650:
            raise Refused("project retention must be 0..3650 days")
        identity = root.stat()
        if not capture_identity and (spec.get("dev"), spec.get("ino")) != (identity.st_dev, identity.st_ino):
            raise Refused("enrolled root identity changed or missing")
        return {"path": str(root), "project": str(project), "session": spec["session"],
                "days": days, "dev": identity.st_dev, "ino": identity.st_ino}

    def enroll(self, project, root, session, days):
        spec = self.validate_project_root({"project": str(project), "path": str(root),
                                          "session": session, "days": days}, capture_identity=True)
        existing = self.config.get("project_scratch", [])
        if len(existing) >= 16:
            raise Refused("project scratch root limit reached")
        for old in existing:
            if not isinstance(old, dict) or not isinstance(old.get("path"), str):
                raise Refused("invalid enrollment; remove it before adding roots")
            p = Path(old["path"])
            if p.is_relative_to(Path(spec["path"])) or Path(spec["path"]).is_relative_to(p):
                raise Refused("root already enrolled or overlaps another enrollment")
        # Enrollment authorizes future observed creations, never adopts existing files.
        self.config["project_scratch"] = [*existing, spec]
        self.save_config()
        self.project_roots.append(spec)
        self.audit("enroll", spec)
        return {"enrolled": spec, "note": "Existing files are not adopted. Auto mode is unchanged."}

    def unenroll(self, root):
        path = str(root.expanduser().resolve())
        existing = self.config.get("project_scratch", [])
        remaining = [s for s in existing if not isinstance(s, dict) or s.get("path") != path]
        if len(remaining) == len(existing):
            raise Refused("root is not enrolled")
        self.config["project_scratch"] = remaining
        self.save_config()
        self.project_roots = [s for s in self.project_roots if s["path"] != path]
        self.audit("unenroll", {"path": path})
        return {"unenrolled": path, "note": "Files and tracking records are retained; old plans lose authorization."}

    def managed_roots(self, session):
        return [(self.workspace(session), None), *[(Path(s["path"]), s) for s in self.project_roots
                                                   if s["session"] == session]]

    def snapshot(self, root, *, budget=None):
        """Bounded existence evidence inside an authorized root; never parse code/output."""
        safe_components(root)
        identity = root.stat()
        entries, identities, visited, stack = [], {}, 0, [root]
        limit = MAX_ITEMS if budget is None else budget
        while stack:
            base = stack.pop()
            if base != root:
                self.candidate(base, root)
            with os.scandir(base) as iterator:
                for entry in iterator:
                    visited += 1
                    if visited > limit:
                        raise Refused("scratch snapshot exceeds 2000 entries; use a smaller dedicated directory")
                    p = Path(entry.path)
                    try:
                        self.candidate(p, root)
                    except (ValueError, OSError):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(p)
                    else:
                        entries.append(str(p))
                        existing = entry.stat(follow_symlinks=False)
                        identities[str(p)] = [existing.st_dev, existing.st_ino]
        return {"root": str(root), "dev": identity.st_dev, "ino": identity.st_ino,
                "entries": sorted(entries), "identities": identities, "visited": visited}

    def workspace(self, session):
        if not isinstance(session, str) or not session or len(session) > 512:
            raise Refused("valid session id required")
        key = hashlib.sha256(session.encode()).hexdigest()[:32]
        root = self.scratch / key
        root.mkdir(exist_ok=True, mode=0o700)
        safe_components(root)
        return root

    def candidate(self, path, root):
        p = Path(os.path.abspath(path))
        root = Path(root)
        if p == root or not p.is_relative_to(root):
            raise Refused("outside authorized root")
        parts = p.relative_to(root).parts
        if any(x in PROTECTED or x in SECRETS or x.startswith(".env") for x in parts):
            raise Refused("protected path")
        extensions = (".sqlite", ".sqlite3", ".db", ".pem", ".key")
        database_parts = tuple(ext + tail for ext in (".sqlite", ".sqlite3", ".db")
                               for tail in ("-wal", "-shm", "-journal"))
        if p.name.lower().endswith(extensions + database_parts):
            raise Refused("protected data type")
        safe_components(p)
        safe_components(root)
        return p

    def root_for(self, item):
        if item["kind"] == "tracked":
            if item.get("project_policy") is None:
                return self.workspace(item["session"])
            for spec in self.project_roots:
                if spec == item["project_policy"] and spec["session"] == item["session"]:
                    self.validate_project_root(spec)
                    return Path(spec["path"])
            raise Refused("project scratch policy changed or root is no longer enrolled")
        for spec in self.roots:
            if spec == item.get("policy"):
                self.validate_root(spec)
                return Path(spec["path"])
        raise Refused("maintenance policy changed")

    def heartbeat(self, session, ended=0):
        self.db.execute("INSERT INTO sessions VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET "
                        "seen=excluded.seen,ended=excluded.ended", (session, time.time(), ended))

    def candidates(self, payload, root):
        inputs = payload.get("tool_input")
        names = set()
        if isinstance(inputs, dict):
            for key in ("path", "file_path", "filename"):
                if isinstance(inputs.get(key), str):
                    names.add(inputs[key])
            cmd = inputs.get("command", inputs.get("cmd", ""))
        elif isinstance(inputs, str):
            cmd = inputs
        else:
            cmd = ""
        if isinstance(cmd, str):
            # Only literal arguments. Do not execute/evaluate shell, Python or outputs.
            for line in cmd.splitlines():
                match = re.match(r"^\*\*\* (?:Add|Update) File: (.+)$", line)
                if match:
                    names.add(match[1])
            try:
                names.update(shlex.split(cmd))
            except ValueError:
                pass
            names.update(re.findall(r"[\"']([^\"'\n]+)[\"']", cmd))
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not Path(cwd).is_absolute():
            return []
        found = set()
        for name in sorted(names)[:MAX_ITEMS]:
            if any(c in name for c in ("\0", "\n", "$", "`")):
                continue
            p = Path(name)
            if not p.is_absolute():
                p = Path(cwd) / p
            try:
                found.add(str(self.candidate(p, root)))
            except (ValueError, OSError):
                pass
        return sorted(found)

    def hook(self, payload):
        event = payload.get("hook_event_name")
        session = payload.get("session_id")
        root = self.workspace(session)
        with self.transaction():
            self.heartbeat(session, int(event == "SessionEnd"))
            now = time.time()
            self.db.execute("DELETE FROM pending WHERE created < ?", (now - LEASE,))
            self.db.execute("DELETE FROM plans WHERE created < ?", (now - PLAN_TTL,))
            if event in ("PreToolUse", "PostToolUse"):
                call = payload.get("tool_use_id")
                if not isinstance(call, str) or not call:
                    return {"ignored": "missing tool_use_id"}
                roots = self.managed_roots(session)
                paths = sorted({p for managed, _ in roots for p in self.candidates(payload, managed)})[:MAX_ITEMS]
                if event == "PreToolUse":
                    absent = [p for p in paths if not os.path.lexists(p)]
                    literal_identities = []
                    for p in paths:
                        try:
                            existing = Path(p).lstat()
                            if stat.S_ISREG(existing.st_mode):
                                literal_identities.append([existing.st_dev, existing.st_ino])
                        except OSError:
                            pass
                    snapshots = []
                    turn = payload.get("turn_id")
                    ambiguous = False
                    for pending in self.db.execute("SELECT call,paths FROM pending WHERE session=? AND created>?",
                                                   (session, now - LEASE)).fetchall():
                        prior = json.loads(pending["paths"])
                        if not isinstance(prior, dict) or prior.get("turn") != turn:
                            ambiguous = True
                            if isinstance(prior, dict):
                                prior["snapshots"] = []
                                self.db.execute("UPDATE pending SET paths=? WHERE session=? AND call=?",
                                                (compact(prior), session, pending["call"]))
                    if ambiguous:
                        self.audit("coverage-skipped", {"session": session,
                            "reason": "overlapping turn or legacy pending tool; literal tracking only"})
                    budget = MAX_ITEMS
                    for managed, policy in ([] if ambiguous else roots):
                        if budget <= 0:
                            self.audit("coverage-skipped", {"session": session, "root": str(managed),
                                                            "reason": "snapshot budget exhausted"})
                            continue
                        try:
                            snap = self.snapshot(managed, budget=budget)
                            budget -= snap["visited"]
                            snap["policy"] = policy
                            snapshots.append(snap)
                        except (ValueError, OSError) as e:
                            budget = 0
                            self.audit("coverage-skipped", {"session": session, "root": str(managed),
                                                            "reason": str(e)})
                    # Even a call with no new paths may read/write tracked files.
                    # Keep a lease for every observed call, not just file creation.
                    self.db.execute("INSERT OR REPLACE INTO pending VALUES (?,?,?,?)",
                                    (session, call, now, compact({"absent": absent, "snapshots": snapshots,
                                                                 "turn": turn,
                                                                 "literal_identities": literal_identities})))
                    return {"observed": len(absent)}
                row = self.db.execute("SELECT paths FROM pending WHERE session=? AND call=?",
                                      (session, call)).fetchone()
                self.db.execute("DELETE FROM pending WHERE session=? AND call=?", (session, call))
                count = 0
                if row:
                    evidence = json.loads(row[0])
                    # Schema-1 pending records from previous versions remain readable.
                    absent = evidence if isinstance(evidence, list) else evidence["absent"]
                    found = set(absent).intersection(paths)
                    known_identities = set()
                    if isinstance(evidence, dict):
                        known_identities = {tuple(identity) for snap in evidence.get("snapshots", [])
                                            for identity in snap.get("identities", {}).values()}
                        known_identities.update(tuple(identity) for identity in evidence.get("literal_identities", []))
                        budget = MAX_ITEMS
                        for snap in evidence.get("snapshots", []):
                            managed = next((r for r, policy in roots if str(r) == snap["root"]
                                            and policy == snap.get("policy")), None)
                            if managed is None:
                                continue
                            if budget <= 0:
                                self.audit("coverage-skipped", {"session": session, "root": str(managed),
                                                                "reason": "snapshot budget exhausted"})
                                continue
                            try:
                                after = self.snapshot(managed, budget=budget)
                                budget -= after["visited"]
                                if (after["dev"], after["ino"]) != (snap["dev"], snap["ino"]):
                                    raise Refused("scratch root changed during tool call")
                                found.update(set(after["entries"]) - set(snap["entries"]))
                            except (ValueError, OSError) as e:
                                budget = 0
                                self.audit("coverage-skipped", {"session": session, "root": str(managed),
                                                                "reason": str(e)})
                    for name in sorted(found)[:MAX_ITEMS]:
                        try:
                            managed, policy = next((r, s) for r, s in roots
                                                   if Path(name) != r and Path(name).is_relative_to(r))
                            if policy is not None:
                                self.validate_project_root(policy)
                            p = self.candidate(Path(name), managed)
                            existing = p.lstat()
                            if (existing.st_dev, existing.st_ino) in known_identities:
                                continue
                            fp = fingerprint(p)
                            if (fp["dev"], fp["ino"]) in known_identities:
                                continue  # Renaming an existing file is not new ownership.
                            category = "test" if p.name.startswith(("test_", "tmp_test_")) else "temp"
                            if "cron-output" in p.relative_to(managed).parts:
                                category = "cron-output"
                            self.db.execute("INSERT OR IGNORE INTO tracked VALUES (?,?,?,?,?,?)",
                                            (str(p), session, str(payload.get("turn_id", "")),
                                             category, now, compact(fp)))
                            count += 1
                        except (OSError, ValueError):
                            continue
                    self.audit("tracked", {"session": session, "count": count})
                return {"tracked": count}
            if event == "SessionStart":
                self.audit("session-start", {"session": session})
        if event in ("Stop", "SessionEnd", "SessionStart"):
            if event == "Stop" and not isinstance(payload.get("turn_id"), str):
                return {"ignored": "Stop missing turn_id"}
            plan = self.plan("quick", session=session,
                             turn=payload.get("turn_id") if event == "Stop" else None,
                             stale_only=event == "SessionStart",
                             include_busy=self.config["auto"] == "preview")
            if self.config["auto"] == "quarantine" and plan["items"]:
                result = self.apply(plan["plan_id"])
            else:
                result = {"preview": plan}
            if event == "SessionStart":
                result["workspace"] = str(root)
            return result
        return {"ignored": event}

    def plan(self, scope="quick", session=None, turn=None, stale_only=False,
             include_busy=False):
        # A preview may inspect busy files without authorizing a move. Automatic
        # quarantine keeps the pending guard here; move() always rechecks it.
        now = time.time()
        items, skipped, blocked = [], [], []
        with self.transaction():
            active = {r["id"] for r in self.db.execute("SELECT * FROM sessions WHERE ended=0 AND seen>?",
                                                      (now - LEASE,))}
            busy = {r["session"] for r in self.db.execute("SELECT session FROM pending WHERE created>?",
                                                        (now - LEASE,))}
            for r in self.db.execute("SELECT * FROM tracked ORDER BY created LIMIT ?", (MAX_ITEMS,)):
                if stale_only and r["session"] in active:
                    continue
                if session and not stale_only and r["session"] != session:
                    continue
                if not session and r["session"] in active:
                    continue
                if turn is not None and r["turn"] != turn:
                    continue
                project_policy = next((s for s in self.project_roots if s["session"] == r["session"]
                                       and Path(r["path"]).is_relative_to(Path(s["path"]))), None)
                retention = project_policy["days"] * 86400 if project_policy else RETENTION.get(r["category"])
                if retention is None or now - r["created"] < retention:
                    continue
                obstruction = {"path": r["path"], "reason": "session has a pending tool"}
                if r["session"] in busy and not include_busy:
                    skipped.append(obstruction)
                    continue
                item = {"kind": "tracked", "path": r["path"], "session": r["session"],
                        "fp": json.loads(r["fp"])}
                if project_policy:
                    item["project_policy"] = project_policy
                try:
                    p = self.candidate(Path(r["path"]), self.root_for(item))
                    if fingerprint(p) != item["fp"]:
                        raise Refused("modified since tracking")
                    items.append(item)
                    if r["session"] in busy:
                        blocked.append(obstruction)
                except (OSError, ValueError) as e:
                    skipped.append({"path": r["path"], "reason": str(e)})
            if scope == "deep":
                self.scan_maintenance(items, skipped)
            pid = uuid.uuid4().hex
            self.db.execute("DELETE FROM plans WHERE created < ?", (now - PLAN_TTL,))
            self.db.execute("INSERT INTO plans VALUES (?,?,?,0)", (pid, now, compact(items)))
            self.audit("plan", {"id": pid, "scope": scope, "count": len(items),
                                "blocked": len(blocked), "skipped": len(skipped)})
        return {"plan_id": pid, "expires_in_seconds": PLAN_TTL, "scope": scope,
                "items": items, "skipped": skipped, "blocked": blocked,
                "bytes": sum(i["fp"]["size"] for i in items),
                "note": "Preview only. Apply rechecks pending tools and file identity; "
                        "blocked candidates are included in the byte total."}

    def scan_maintenance(self, items, skipped):
        visited = 0
        for spec in self.roots:
            root = Path(spec["path"])
            self.validate_root(spec)
            for base, dirs, files in os.walk(root, followlinks=False):
                dirs[:] = sorted(d for d in dirs if d not in PROTECTED and not d.startswith("."))
                for name in sorted(files):
                    visited += 1
                    if visited > MAX_ITEMS:
                        raise Refused("maintenance scan exceeds 2000 files; choose a smaller root")
                    p = Path(base) / name
                    try:
                        p = self.candidate(p, root)
                        if spec["kind"] == "logs" and p.suffix.lower() not in (".log", ".jsonl", ".txt"):
                            continue
                        fp = fingerprint(p)
                        # ctime protects recently rotated/copied files even with old mtime.
                        modified = max(fp["mtime"], fp["ctime"]) / 1e9
                        if time.time() - modified < spec["days"] * 86400:
                            continue
                        items.append({"kind": "maintenance", "path": str(p), "policy": spec, "fp": fp})
                    except (OSError, ValueError) as e:
                        skipped.append({"path": str(p), "reason": str(e)})

    def apply(self, pid):
        results, skipped = [], []
        with self.transaction():
            row = self.db.execute("SELECT * FROM plans WHERE id=?", (pid,)).fetchone()
            if not row or row["used"] or time.time() - row["created"] > PLAN_TTL:
                raise Refused("unknown, used or expired plan")
            self.db.execute("UPDATE plans SET used=1 WHERE id=?", (pid,))
            items = json.loads(row["items"])
        for item in items:
            try:
                mid = self.move(item)
                results.append(mid)
            except (OSError, ValueError, sqlite3.Error) as e:
                skipped.append({"path": item["path"], "reason": str(e)})
        return {"quarantined": results, "skipped": skipped,
                "note": "Disk space is reclaimed only after explicit purge."}

    def move(self, item):
        with self.transaction():
            root = self.root_for(item)
            p = self.candidate(Path(item["path"]), root)
            if item["kind"] == "tracked":
                row = self.db.execute("SELECT * FROM tracked WHERE path=?", (str(p),)).fetchone()
                if not row or row["session"] != item["session"] or json.loads(row["fp"]) != item["fp"]:
                    raise Refused("tracking record changed")
                pending = self.db.execute("SELECT 1 FROM pending WHERE session=? AND created>?",
                                          (item["session"], time.time() - LEASE)).fetchone()
                if pending:
                    raise Refused("session has a pending tool")
                policy = item.get("project_policy")
                retention = policy["days"] * 86400 if policy else RETENTION.get(row["category"])
                if retention is None or time.time() - row["created"] < retention:
                    raise Refused("retention has not elapsed")
            if fingerprint(p) != item["fp"]:
                raise Refused("file changed after preview")
            qdir = root / ".codex-disk-cleanup-quarantine"
            qdir.mkdir(exist_ok=True, mode=0o700)
            safe_components(qdir)
            mid = uuid.uuid4().hex
            dest = qdir / mid
            # Durable intent before filesystem change: recover can reconcile a crash.
            self.db.execute("INSERT INTO moves VALUES (?,?,?,?,?,'moving',?)",
                            (mid, str(p), str(dest), str(root), compact(item["fp"]), time.time()))
        safe_components(p)
        if fingerprint(p) != item["fp"]:
            raise Refused("file changed before move")
        os.rename(p, dest)  # Same root/filesystem; no recursive directory deletion.
        if not same_content(fingerprint(dest), item["fp"]):
            self.audit("needs-recovery", {"id": mid})
            raise Refused("identity changed during move; inspect quarantine and recover")
        with self.transaction():
            self.db.execute("UPDATE moves SET state='quarantined' WHERE id=?", (mid,))
            self.db.execute("DELETE FROM tracked WHERE path=?", (str(p),))
            self.audit("quarantine", {"id": mid, "path": str(p)})
        return mid

    def quarantine_path(self, row):
        root = Path(row["root"])
        authorized = root.is_relative_to(self.scratch) and root.parent == self.scratch
        authorized = authorized or any(root == Path(r["path"]) for r in self.roots)
        for spec in self.project_roots:
            if root == Path(spec["path"]):
                self.validate_project_root(spec)
                authorized = True
        if not authorized:
            raise Refused("quarantine root no longer authorized")
        safe_components(root)
        p = root / ".codex-disk-cleanup-quarantine" / row["id"]
        if str(p) != row["dest"] or not re.fullmatch(r"[a-f0-9]{32}", row["id"]):
            raise Refused("invalid quarantine record")
        safe_components(p)
        return p

    def restore(self, mid):
        with self.transaction():
            row = self.db.execute("SELECT * FROM moves WHERE id=?", (mid,)).fetchone()
            if not row or row["state"] != "quarantined":
                raise Refused("not a quarantined item; recover incomplete moves first")
            src = self.quarantine_path(row)
            dest = self.candidate(Path(row["source"]), Path(row["root"]))
            if not same_content(fingerprint(src), json.loads(row["fp"])):
                raise Refused("quarantined file changed")
            if os.path.lexists(dest) or not dest.parent.is_dir():
                raise Refused("restore destination occupied or parent missing")
            # Persist restoration intent so interrupted link/unlink can be recovered.
            self.db.execute("UPDATE moves SET state='restoring' WHERE id=?", (mid,))
        if os.name == "nt":
            os.rename(src, dest)  # Windows rename refuses existing destinations.
        else:
            os.link(src, dest, follow_symlinks=False)  # Exclusive create, never overwrite.
            src.unlink()
        with self.transaction():
            self.db.execute("UPDATE moves SET state='restored' WHERE id=?", (mid,))
            self.audit("restore", {"id": mid})
        return {"restored": str(dest)}

    def purge(self, mid):
        with self.transaction():
            row = self.db.execute("SELECT * FROM moves WHERE id=?", (mid,)).fetchone()
            if not row or row["state"] != "quarantined":
                raise Refused("not a quarantined item")
            p = self.quarantine_path(row)
            if not same_content(fingerprint(p), json.loads(row["fp"])):
                raise Refused("quarantined file changed")
            self.db.execute("UPDATE moves SET state='purging' WHERE id=?", (mid,))
        p.unlink()
        with self.transaction():
            self.db.execute("UPDATE moves SET state='purged' WHERE id=?", (mid,))
            self.audit("purge", {"id": mid, "bytes": json.loads(row["fp"])["size"]})
        return {"purged": mid}

    def recover(self):
        results = []
        with self.transaction():
            for row in self.db.execute("SELECT * FROM moves WHERE state IN ('moving','restoring','purging')").fetchall():
                state = "needs-review"
                try:
                    dest = self.quarantine_path(row)
                    source = self.candidate(Path(row["source"]), Path(row["root"]))
                    fp = json.loads(row["fp"])
                    if row["state"] == "moving":
                        if not os.path.lexists(source) and same_content(fingerprint(dest), fp):
                            state = "quarantined"
                            self.db.execute("DELETE FROM tracked WHERE path=?", (str(source),))
                        elif not os.path.lexists(dest) and fingerprint(source) == fp:
                            state = "cancelled"
                    elif row["state"] == "restoring":
                        # A crash between hardlink and unlink leaves two names. Do not
                        # auto-delete either; operator inspection is required.
                        if not os.path.lexists(dest) and same_content(fingerprint(source), fp):
                            state = "restored"
                        elif not os.path.lexists(source) and same_content(fingerprint(dest), fp):
                            state = "quarantined"
                    elif not os.path.lexists(dest):
                        state = "purged"
                    elif same_content(fingerprint(dest), fp):
                        state = "quarantined"
                except (OSError, ValueError):
                    pass
                # Ambiguous records remain retryable and are never auto-deleted.
                if state != "needs-review":
                    self.db.execute("UPDATE moves SET state=? WHERE id=?", (state, row["id"]))
                results.append({"id": row["id"], "state": state})
            self.audit("recover", results)
        return {"recovered": results}

    def status(self):
        result = {"version": VERSION, "data": str(self.data), "auto": self.config["auto"],
                  "initialized": self.db is not None, "hooks_seen": False,
                  "maintenance": self.roots, "tracked": [], "quarantine": [], "pending": 0,
                  "pending_sessions": [], "project_scratch": self.project_roots,
                  "project_scratch_errors": self.project_errors}
        if self.db is None:
            result["note"] = "State has not been initialized. Hook trust/dispatch has not been verified."
            return result
        result.update({"hooks_seen": bool(self.db.execute("SELECT 1 FROM sessions LIMIT 1").fetchone()),
                "maintenance": self.roots,
                "tracked": [dict(r) for r in self.db.execute("SELECT path,session,category,created FROM tracked")],
                "quarantine": [dict(r) for r in self.db.execute("SELECT id,source,state,created FROM moves "
                                                                "WHERE state NOT IN ('purged','restored','cancelled')")],
                "pending": self.db.execute("SELECT count(*) FROM pending").fetchone()[0],
                "pending_sessions": [dict(r) for r in self.db.execute(
                    "SELECT session,count(*) AS tools,min(created) AS oldest_created FROM pending "
                    "WHERE created>? GROUP BY session ORDER BY session", (time.time() - LEASE,))]})
        return result


def resolve_data(explicit=None, *, script=None, env=None, home=None):
    """Resolve host allocation from verified legacy cache layout, never glob/guess."""
    env = os.environ if env is None else env
    if explicit is not None:
        return Path(explicit), "explicit"
    for name in ("PLUGIN_DATA", "CLAUDE_PLUGIN_DATA"):
        if env.get(name):
            return Path(env[name]), name
    home = Path.home() if home is None else Path(home)
    codex_home = Path(env.get("CODEX_HOME", str(home / ".codex"))).expanduser().resolve()
    script = Path(__file__) if script is None else Path(script)
    root = script.resolve().parent.parent
    try:
        parts = root.relative_to(codex_home / "plugins" / "cache").parts
    except ValueError:
        parts = ()
    if len(parts) == 3:
        marketplace, name, version = parts
        manifest = root / ".codex-plugin" / "plugin.json"
        # Native loader currently skips Hooks for root Agent Plugins manifests.
        if name != "codex-disk-cleanup" or not re.fullmatch(r"[a-zA-Z0-9_.-]+", marketplace):
            raise Refused("unexpected installed plugin identity")
        if not manifest.is_file() or (root / "plugin.json").exists():
            raise Refused("cannot verify native hook package layout")
        identity = json.loads(manifest.read_text(encoding="utf-8"))
        if identity.get("name") != name or identity.get("version") != version:
            raise Refused("installed manifest identity does not match cache path")
        # Mirrors Codex PluginStore::plugin_data_root, verified in native source.
        return codex_home / "plugins" / "data" / (name + "-" + marketplace), "codex-installation"
    return home / ".local" / "share" / "codex-disk-cleanup", "standalone"


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=None, help="Override plugin state directory")
    p.add_argument("--version", action="version", version=VERSION)
    subs = p.add_subparsers(dest="command", required=True)
    init = subs.add_parser("init", help="Create preview-mode config")
    init.add_argument("--auto", choices=("preview", "quarantine"), default="preview")
    subs.add_parser("status")
    enroll = subs.add_parser("enroll", help="Enroll a dedicated project scratch directory for one session")
    enroll.add_argument("--project", type=Path, required=True)
    enroll.add_argument("--root", type=Path, required=True)
    enroll.add_argument("--session", required=True)
    enroll.add_argument("--days", type=int, default=7)
    enroll.add_argument("--yes", action="store_true")
    unenroll = subs.add_parser("unenroll", help="Withdraw a project scratch enrollment without moving files")
    unenroll.add_argument("--root", type=Path, required=True)
    unenroll.add_argument("--yes", action="store_true")
    subs.add_parser("hook", help="Read one Codex event JSON from stdin")
    ws = subs.add_parser("workspace")
    ws.add_argument("--session", required=True)
    for name in ("dry-run", "quick", "deep"):
        c = subs.add_parser(name)
        if name == "dry-run":
            c.add_argument("--scope", choices=("quick", "deep"), default="quick")
        c.add_argument("--session")
        if name != "dry-run":
            c.add_argument("--apply", metavar="PLAN_ID")
            c.add_argument("--yes", action="store_true")
    for name in ("restore", "purge"):
        c = subs.add_parser(name)
        c.add_argument("id")
        if name == "purge":
            c.add_argument("--yes", action="store_true")
    subs.add_parser("recover")
    subs.add_parser("audit")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    is_hook = args.command == "hook"
    store = None
    try:
        data, data_source = resolve_data(args.data)
        store = Store(data, read_only=args.command == "status")
        if is_hook:
            raw = sys.stdin.buffer.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise Refused("hook payload exceeds 1 MiB")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise Refused("hook payload must be an object")
            result = store.hook(payload)
            event = payload.get("hook_event_name")
            if event == "SessionStart":
                context = ("Codex disk cleanup scratch directory: " + str(store.workspace(payload["session_id"]))
                           + ". Plugin state directory (pass as --data): " + str(store.data)
                           + ". Cleanup script: " + str(Path(__file__).resolve())
                           + ". Plan file locations before writing: put disposable scripts, crops, render checks, "
                           + "contact sheets and staging copies here. Keep final deliverables, reusable assets, "
                           + "source prompts and audit evidence in the project. "
                           + "Pre/PostToolUse use bounded directory snapshots to track newly created files here, "
                           + "including dynamic Python/shell paths. Existing files are not adopted. "
                           + "Project directories require explicit enroll; never enroll a mixed delivery directory. "
                           + "Enrolled project scratch for this session: "
                           + compact([s for s in store.project_roots if s["session"] == payload["session_id"]]) + ". "
                           + "After success, review tracked candidates; preview does not reclaim disk space. "
                           + "Auto mode: " + store.config["auto"] + ". test_* scratch files may be quarantined at Stop.")
                result = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
            elif event == "Stop":
                result = {"continue": True}
            else:
                result = {}
        elif args.command == "init":
            store.config["auto"] = args.auto
            store.save_config()
            result = store.status()
        elif args.command == "enroll":
            if not args.yes:
                raise Refused("enroll requires --yes after reviewing the dedicated directory and retention")
            result = store.enroll(args.project, args.root, args.session, args.days)
        elif args.command == "unenroll":
            if not args.yes:
                raise Refused("unenroll requires --yes")
            result = store.unenroll(args.root)
        elif args.command == "workspace":
            result = {"workspace": str(store.workspace(args.session))}
        elif args.command == "status":
            result = store.status()
            result["data_source"] = data_source
        elif args.command in ("dry-run", "quick", "deep"):
            if getattr(args, "apply", None):
                if not args.yes:
                    raise Refused("--apply requires --yes after reviewing the plan")
                result = store.apply(args.apply)
            else:
                scope = args.scope if args.command == "dry-run" else args.command
                result = store.plan(scope, session=args.session, include_busy=True)
        elif args.command == "restore":
            result = store.restore(args.id)
        elif args.command == "purge":
            if not args.yes:
                raise Refused("purge requires --yes; this permanently deletes the listed item")
            result = store.purge(args.id)
        elif args.command == "recover":
            result = store.recover()
        else:
            result = {"audit": [dict(r) for r in store.db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 100")]}
        print(json.dumps(result, ensure_ascii=False, indent=None if is_hook else 2))
        return 0
    except (OSError, ValueError, sqlite3.Error, KeyError, TypeError) as e:
        # Hooks never interfere with the task; cleanup fails closed, tool continues.
        print("disk-cleanup: " + str(e), file=sys.stderr)
        if is_hook:
            print("{}")
            return 0
        return 1
    finally:
        if store:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
