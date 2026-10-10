---
name: disk-cleanup
description: Inspect or clean Codex scratch files, preview cache and log maintenance, restore quarantined files, or check cleanup status. Use when the user requests disk cleanup or temporary-file management.
---

Use the bundled `scripts/cleanup.py`, resolved two directories above this skill.
Use `python3` on macOS/Linux and `py -3` on Windows. Pass `--data` with the
installed plugin's writable `PLUGIN_DATA` directory when that environment
variable is not inherited by the tool. Do not substitute another state directory
without explaining that it is a separate standalone instance. If the actual data
directory is unavailable, report this and ask for its path rather than guessing.

1. `status` shows policy, tracked files and quarantine IDs.
2. `dry-run --scope quick` previews tracked disposable files.
3. `dry-run --scope deep` also previews explicitly configured old cache/log files.
4. `quick --apply PLAN_ID --yes` or `deep --apply PLAN_ID --yes` moves the reviewed
   files to quarantine. Plain `quick` and `deep` only preview. Honor an existing
   user request to clean within the shown scope; do not repeatedly ask approval.
5. `restore ID` restores one file without overwriting an existing path.
6. `purge ID --yes` permanently deletes one quarantined file. Run only when the
   user authorizes permanent deletion of that item. Explain that quarantine alone
   does not reclaim disk space.
7. `recover` reconciles interrupted operations. Show `needs-review` records to the
   user; do not delete ambiguous files or edit the database to clear them.

Put disposable intermediate files in the scratch path supplied by SessionStart.
Use literal file paths in tool arguments. Hooks do not inspect command outputs
or evaluate embedded code. Keep final deliverables and permanent tests in the
user's workspace. `test_*` scratch files have zero retention and can be moved at
Stop when auto quarantine has explicitly been enabled. Other temporary files
retain seven days; `cron-output/` retains fourteen days.

Never clean a project by filename pattern. Never scan sessions, memories, auth,
skills, plugins, SQLite files, Git trees or general browser/package caches.
Do not enable automatic mode, add maintenance roots, or bypass host hook trust
as a side effect of a status/preview request. Installation does not enable auto
quarantine; the default is preview.
