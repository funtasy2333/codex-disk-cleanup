# Codex Disk Cleanup

[中文](../README.md)

A local Codex plugin for evidence-based scratch-file lifecycle management.
Python 3.10+, standard library only. Version 0.1.2 fixes native hook registration and SessionEnd timeout compatibility; it is
not a claim of long-term production stability.

Source candidate 0.1.3 fixes a preview command's own pending lease hiding the
selected session's candidates and reports execution blockers. The Git install
commands below still reference published 0.1.2. Publication, installation and
native acceptance of 0.1.3 remain outstanding.

## Install

```sh
codex plugin marketplace add funtasy2333/codex-disk-cleanup --ref v0.1.2
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

SessionStart provides an isolated session scratch directory. Only literal paths
proven absent before and present after the same tool call are tracked.
`test_*` / `tmp_test_*` files can be quarantined at the current turn's Stop or
SessionEnd; other scratch files retain seven days, and `cron-output/` files
retain fourteen days. Modified files are skipped. Pending tool records and
session activity leases last 24 hours. SessionStart sweeps only ended or stale
sessions. For unusually long-running jobs, keep preview mode enabled.
Dynamic shell/code paths and outputs are not evaluated. Deliverables and
permanent tests belong in the project, not scratch.

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
