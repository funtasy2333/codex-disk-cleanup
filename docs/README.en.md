# Codex Disk Cleanup

[中文](../README.md)

A local Codex plugin for evidence-based scratch-file lifecycle management.
Python 3.10+, standard library only. Published version: **0.1.4**. This branch
contains an unreleased, uninstalled **0.1.5 source candidate** that discovers new
dedicated session temporary directories; scratch becomes optional. Preview is the
default. Explicit quarantine mode moves files into reversible quarantine;
permanent deletion is separate.

All 182 isolated candidate tests pass. Cross-platform CI and upgraded native
Hook acceptance remain outstanding; see the validation record.

## Install

```sh
codex plugin marketplace add funtasy2333/codex-disk-cleanup --ref v0.1.4
codex plugin add codex-disk-cleanup@codex-disk-cleanup-marketplace
```

Review and trust the hooks using your client's supported flow. Installation does
not automatically trust hooks. This repository never bypasses trust or edits
global configuration. The release ZIP is also available for supported manual
desktop installation flows. Hooks require local orchestration and execution;
cloud-orchestrated Work cannot run these local plugin command hooks.
Hook-bearing plugins currently cannot be submitted to the public OpenAI directory.
See [official hooks](https://learn.chatgpt.com/docs/hooks) and
[packaging guidance](https://developers.openai.com/plugins/build/plugins).

Before upgrading, stop active chats; restart Desktop after updating. The host
may remove old version caches while an active chat still references their hook
commands, causing missing-file errors. Restarting loads the new definitions.
Do not patch installed caches or trust records as a workaround.

## Usage

`PLUGIN_DIR` is the installed package directory. Run `status` without `--data`
first: it verifies the native cache layout and matching manifest, then derives
the host allocation. Check `data_source` and use the returned `data` as `DATA_DIR`.
Host `PLUGIN_DATA`/`CLAUDE_PLUGIN_DATA` and explicit `--data` take precedence.
Status does not initialize missing state; `initialized: false` is not evidence
of hook dispatch. Source users can choose a dedicated `--data` directory for a
separate CLI instance.

The current native loader skips hooks in root Agent Plugins `plugin.json`
packages, so the installable package uses only `.codex-plugin/plugin.json`.
The portable manifest is a documentation example outside the package. After
installation, Settings → Hooks should list five Codex Disk Cleanup hooks. See
[verified compatibility evidence](provenance.md).

```sh
python3 "$PLUGIN_DIR/scripts/cleanup.py" status
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" dry-run --scope quick
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" dry-run --scope deep
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" quick --apply PLAN_ID --yes
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" restore QUARANTINE_ID
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" purge QUARANTINE_ID --yes
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" recover
```

On Windows use `py -3` and PowerShell path variable syntax. Plain `quick` and
`deep` only preview. Plans expire in 15 minutes and cannot be replayed. Apply
revalidates policy, metadata, SHA-256 and pending tools. `--session SESSION_ID`
selects a specific session; without it, manual plans skip active sessions.

From 0.1.3, manual previews display pending candidates with exact paths, bytes
and plan IDs. `blocked` lists paths currently prevented from being moved;
`bytes` includes these candidates and does not mean immediately reclaimable
space. Fingerprint, retention and session checks still apply. Read-only status
adds `pending_sessions`, grouping live tools and oldest timestamps by session.
The existing `pending` count includes all records, including expired leases
awaiting normal Hook housekeeping.

Apply still refuses live pending tools, including a native apply command's own
tool lease. Wait for tools to finish, then use an authorized lifecycle flow or
a separate terminal. Never delete pending records to bypass the guard.
Preview-mode lifecycle plans also display blocked candidates; automatic
quarantine plans skip them with a reason.

Default auto mode is **preview**. To explicitly enable reversible automatic
cleanup run `init --auto quarantine`; `init --auto preview` disables it again.
Quarantine does not reclaim disk space. Only an explicit per-item `purge ID --yes`
permanently removes a quarantined file. `restore` never overwrites another file.

SessionStart provides an isolated session scratch directory. Literal paths and
bounded snapshots establish absence/identity evidence across the same tool call.
`test_*` / `tmp_test_*` files can be quarantined at the current turn's Stop or
SessionEnd; other scratch files retain seven days, and `cron-output/` files
retain fourteen days. Modified files are skipped. Pending tool records and
session activity leases last 24 hours. SessionStart sweeps only ended or stale
sessions. For unusually long-running jobs, keep preview mode enabled.
Dynamic shell/code paths and outputs are not evaluated. Deliverables and
permanent tests belong in the project, not scratch.

## 0.1.5 source candidate: observe actual temporary locations

Published/installed 0.1.4 remains unchanged. This candidate has not been released,
installed or accepted through native desktop dispatch. Scratch is optional:
literal tool-input paths can identify new dedicated OS temporary directories.
Pre pins an absent candidate and existing parent/base identities; matching Post
checks session, call, turn and the safe new directory identity. Only stdlib OS
temporary bases and the canonical POSIX /tmp alias are permitted. No whole-temp
scan, code evaluation or tool-output ownership inference occurs. Existing/shared
directories and random directories not mentioned in inputs are not adopted.

Initial contents are metadata-only review candidates, never cleanup-owned.
Subsequent complete bounded snapshots can track new files. A failed first call
may bind a directory but cannot adopt its contents; later failed calls do not
adopt new output. Discovery uses seven-day retention even for test_* filenames.
Pending, protected-path, Git/link/hardlink, fingerprint and reversible quarantine
checks remain. Another session's explicit temp-root access also blocks moves
and invalidates overlapping creation evidence, even if that tool finishes first.

Each phase shares 2000 directory entries. At most16 discovered roots per session
and2000 global root records/2000 review observations are retained. Incomplete,
ambiguous, mismatched or changed-root evidence fails closed. Oversized tool inputs
retain an unknown-access pending lease that blocks all moves until completion,
and invalidate concurrent creation evidence. `status` exposes
`discover_temp`, `discovered_temp`, `discovered_temp_errors`, `review_candidates`.
Review-only observations of explicit ordinary project paths do not read/hash
contents or produce executable plans. The separate `generated-preview` remains
read-only; no complete arbitrary-project or generated-image tracking is claimed.

```sh
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" init --discover-temp off
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" init --discover-temp on
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" forget-temp --root /absolute/temp/task --yes
```

Discovery defaults on for future candidate-version calls; changing it preserves
auto mode and other policy. Disable revokes discovery-based move plans but allows
restore. Forget is metadata-only and refuses roots with unresolved quarantine:
restore, explicitly purge or reconcile first. Optional schema1 state tables keep
old read-only data working without initialization. Existing historical temp
folders are not retroactively adopted. Full native lifecycle and cross-platform
acceptance of this candidate remain separate checks.

## 0.1.4: project scratch and dynamic paths

Version 0.1.4 adds coverage for project scratch and dynamic paths. Full native
lifecycle acceptance remains pending upgrade and restart. Plan locations before writing: disposable
scripts, crops, render checks, reference contact sheets and staging copies go
to scratch; final files, reusable source assets, source prompts and audit
evidence stay in the project. Superseded attempts retained as audit evidence
are not disposable solely because their names say draft.

Matching pre/post calls compare bounded existence snapshots inside authorized
roots, capturing variable Python/shell paths without evaluating code or output.
All roots share a 2000-entry budget per phase. Overflow, access failures,
overlapping turns and legacy pending calls suspend new adoption, including
literal destinations, and record coverage-skipped. No post without a matching pre
can adopt files. Host generated-image source caches are not automatically enrolled or cleaned;
use the separate read-only comparison below.

Explicitly enroll an existing dedicated subdirectory for one actual session:

```sh
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" enroll \
  --project /absolute/project --root /absolute/project/.tmp/session-id \
  --session ACTUAL_SESSION_ID --days 7 --yes
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" unenroll \
  --root /absolute/project/.tmp/session-id --yes
```

Enrollment binds device/inode and session; at most 16 nonoverlapping roots are
allowed. Existing files and auto mode are unchanged. Project retention overrides
filename categories; default is seven days, explicit --days 0 makes new files
immediately eligible subject to pending guards. Withdrawal moves no files and
invalidates old plans. Status exposes project_scratch and project_scratch_errors;
missing/changed roots can still be withdrawn. Never enroll an entire project or
a mixed delivery/audit directory. Git trees, protected paths, home/Codex data,
links and hardlinks stay protected; Git projects use external plugin scratch.
Quarantine, restore and explicit purge keep their confirmation/identity checks.
Historical files may be listed for review but never receive fabricated tracking
records. Default remains preview.

### Read-only host generated-image comparison

```sh
python3 "$PLUGIN_DIR/scripts/cleanup.py" generated-preview \
  --session ACTUAL_SESSION_ID --copy-root /absolute/project/saved-images
```

The source scope is exactly CODEX_HOME/generated_images/UUID, not other sessions
or all Codex data. Repeat --copy-root for explicit archive directories outside
Codex home; without copies, no backup is inferred. Optional --codex-home selects
the source home for this command only. A shared 2000-entry budget bounds source
and copy traversal. Symlinks, hardlinks, protected paths and oversized files are
not candidate evidence.

Every source reports its fingerprint, bytes and exact SHA-256 matching copies.
verified-duplicate-review-required means a copy was observed, not that the source
is unused; moving originals may affect conversation images or later edits.
no-copy-verified preserves uncertainty. The command creates no plugin state,
tracking or executable plan, accepts no apply/purge and never moves files.

## Maintenance

Edit the actual data directory's `config.json` to explicitly enroll existing
absolute directories within `CODEX_HOME/cache` or `CODEX_HOME/logs`:

```json
{
  "schema": 1,
  "auto": "preview",
  "maintenance": [
    {"path": "/Users/yourname/.codex/logs", "kind": "logs", "days": 30}
  ]
}
```

Use the same `CODEX_HOME` environment for configuration, preview and apply.
Retention is 1..3650 days; age uses the newer of mtime and ctime. Logs are limited
to `.log`, `.jsonl`, `.txt`. Git trees, secrets, sessions, memories, skills, plugins,
databases, symlinks/reparse points and hardlinks remain protected. Hooks never
run maintenance. Close applications writing into enrolled directories before
manual maintenance; arbitrary OS-level open-file detection is not implemented.

## Verification and limitations

```sh
python3 -m unittest discover -s tests -v
python3 tools/package.py --check
python3 tools/package.py
```

CI covers Linux/macOS/Windows and Python 3.10/3.13. Each file is limited to 64 MiB,
maintenance scans to 2000 entries; no directories are deleted recursively.
SQLite WAL transactions, bounded audits and durable operation intents support
concurrent hooks and crash recovery. Ambiguous recovery preserves files and
reports `needs-review`.

Designed for trusted local filesystems, not protection against a malicious
process racing the same directory under the same OS identity. Use
[SECURITY.md](../SECURITY.md) and [validation](validation.md) for precise limits.
Hermes-inspired, independently rewritten, MIT licensed.
