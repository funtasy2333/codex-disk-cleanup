# Codex Disk Cleanup 0.1.4

Local Codex scratch-file lifecycle plugin. Python 3.10+, standard library only.
Initial testable release; default behavior is preview, not automatic deletion.

Installation, Chinese/English instructions, safety boundaries and validation:
[project documentation](https://github.com/funtasy2333/codex-disk-cleanup).

Review and trust the bundled hooks using the host's supported flow. This ZIP
does not deploy scripts to cloud-orchestrated Work or bypass hook trust.
In a new chat, SessionStart supplies the session scratch path and plugin data
directory. Ordinary tools may not inherit `PLUGIN_DATA`; pass that actual data
directory explicitly when running the script. A different data directory is a
separate instance.

```sh
python3 scripts/cleanup.py --data /absolute/plugin-data status
python3 scripts/cleanup.py --data /absolute/plugin-data dry-run --scope quick
python3 scripts/cleanup.py --data /absolute/plugin-data quick --apply PLAN_ID --yes
python3 scripts/cleanup.py --data /absolute/plugin-data restore QUARANTINE_ID
python3 scripts/cleanup.py --data /absolute/plugin-data purge QUARANTINE_ID --yes
```

Run from this directory or use the absolute script path. Windows: use `py -3`.
Plain `quick` and `deep` only preview. Plans expire after 15 minutes. Quarantine
does not reclaim disk space; purge permanently deletes one selected item.

Select the current session with `--session ACTUAL_SESSION_ID`; otherwise manual
previews omit active sessions. Pending candidates remain visible in previews,
with exact paths, bytes and plan IDs. `blocked` lists pending execution guards;
byte totals include blocked candidates. Apply still refuses live pending tools,
including its own native tool lease. Wait for tools to finish and use the normal
lifecycle flow or a separate terminal for authorized execution. Never delete
pending records to bypass this guard. `status` includes `pending_sessions` for
live tool counts and oldest timestamps.

Explicitly enable automatic quarantine with `init --auto quarantine`; return to
preview with `init --auto preview`. Auto mode only handles newly observed files in managed scratch roots, including
explicitly enrolled project scratch, never maintenance roots. `test_*` files can be moved at Stop. Keep permanent
tests and deliverables in the project. Other scratch files retain seven days,
and `cron-output/` retains fourteen days. Modified files and pending tools block
cleanup. Session/pending leases last 24 hours; use preview for longer jobs.

Maintenance is opt-in in the actual data directory's `config.json`, and only
within `CODEX_HOME/cache` or `CODEX_HOME/logs`. Close writers before manual deep
maintenance. Git trees, credentials, configuration, databases and their sidecars,
sessions, memories, skills, plugins, links/reparse points and hardlinks are
protected. No recursive directory deletion. No hostile-process filesystem
sandbox or network-filesystem guarantees. `recover` preserves ambiguous records
for inspection. See the repository SECURITY.md before enrollment.

## Project scratch and dynamic file creation (0.1.4)

This source candidate adds bounded Pre/PostToolUse directory snapshots, so Python
loops and variable paths can be observed inside managed roots. A matching pre
call is required; preexisting files are never adopted. Directory snapshots do
not evaluate shell code or tool output. The combined budget is 2000 entries per
phase; failures are recorded as coverage-skipped and fall back to literal paths.
Overlapping turns or legacy pending calls also disable dynamic snapshots.

Explicitly enroll an existing dedicated subdirectory for one actual session:

```sh
python3 scripts/cleanup.py --data /absolute/plugin-data enroll \
  --project /absolute/project --root /absolute/project/.tmp/session-id \
  --session ACTUAL_SESSION_ID --days 7 --yes
python3 scripts/cleanup.py --data /absolute/plugin-data unenroll \
  --root /absolute/project/.tmp/session-id --yes
```

The root must exist, be a strict project descendant, and retain its recorded
device/inode identity. Enrollment leaves existing files and auto mode unchanged.
Project retention applies to every observed file, including test_*; explicit
--days 0 makes new files immediately eligible, subject to pending guards.
Do not enroll an entire project or a mixed delivery/archive directory. Git trees,
protected paths, home/Codex data, overlapping roots and links are refused. For
Git projects, use the plugin's external scratch. Withdrawal moves no files and
invalidates old plans. Status lists project_scratch and project_scratch_errors.
Quarantine/restore/purge retain their existing confirmation and identity rules.

Plan file locations before writing: crops, render checks, reference contact
sheets, temporary scripts and staging copies belong in scratch; final files,
reusable assets, source prompts and audit evidence belong in the project. Host generated-image source caches are not automatically cleaned. Use
generated-preview --session ACTUAL_UUID --copy-root ABS_ARCHIVE to inspect
this exact session source directory and SHA-256 matching project copies. This
read-only command creates no state, tracking or executable plan; copies do not
prove originals are unused by conversation viewing or editing.
