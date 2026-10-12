---
name: disk-cleanup
description: Inspect or clean Codex scratch files, preview cache and log maintenance, restore quarantined files, or check cleanup status. Use when the user requests disk cleanup or temporary-file management.
---

Use the bundled `scripts/cleanup.py`, resolved two directories above this skill.
Use `python3` on macOS/Linux and `py -3` on Windows. Pass `--data` with the
installed plugin's writable `PLUGIN_DATA` directory when that environment
variable is not inherited by the tool. Run `status` directly from the installed
script first: it resolves the native host data allocation from the verified
`plugins/cache/<marketplace>/<name>/<version>` layout and matching legacy
manifest. `status` is read-only and reports `initialized: false` when Hooks have
not created state. Do not ask the user for a path when this resolver succeeds.
Check `data_source`: `codex-installation` is the installed instance; `standalone`
is a separate CLI instance. For an unusual source layout without environment or
verified installed identity, report the limitation rather than inventing a path.
Missing state does not mean cleanup has run successfully. Hooks must appear in
the native registry and be reviewed/trusted before dispatch can be confirmed.

1. `status` shows policy, tracked files, quarantine IDs and `pending_sessions`
   (live tool counts and oldest timestamps). `pending` counts all stored leases.
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

Use `--session ACTUAL_SESSION_ID` to preview the current session; without it,
manual previews skip active sessions. Manual previews include pending candidates
and list them in `blocked`, preserving exact paths, fingerprints, bytes and plan
IDs. `bytes` includes blocked candidates. Preview visibility does not authorize
execution: apply and automatic quarantine still recheck and refuse live pending
tools. Do not delete leases or bypass that guard. A native apply command can be
blocked by its own tool lease; report the reason and use the supported lifecycle
flow or a separate terminal after tools finish, within the user's authorization.
Preview-mode lifecycle plans also show pending candidates; quarantine-mode plans
skip them with a reason. Neither mode relaxes session, turn or retention filters.

Put disposable intermediate files in the scratch path supplied by SessionStart.
Prefer literal paths in tool arguments. Matching Hooks also compare bounded
directory snapshots inside managed roots, so dynamic paths can be tracked
without inspecting command outputs or evaluating code. Keep final deliverables and permanent tests in the
user's workspace. `test_*` scratch files have zero retention and can be moved at
Stop when auto quarantine has explicitly been enabled. Other temporary files
retain seven days; `cron-output/` retains fourteen days.

Never clean a project by filename pattern. Never scan sessions, memories, auth,
skills, plugins, SQLite files, Git trees or general browser/package caches.
Do not enable automatic mode, add maintenance roots, or bypass host hook trust
as a side effect of a status/preview request. Installation does not enable auto
quarantine; the default is preview.


Before a file-producing task, choose locations by purpose. Put disposable scripts,
crops, render verification images, reference contact sheets and staging copies in
the injected scratch. Keep final outputs, reusable/editable source assets, source
prompts, regression tests and audit evidence in the project. A source attempt
explicitly retained for audit is not disposable solely because it is superseded.

Project scratch is opt-in. Only after the user identifies a dedicated existing
subdirectory may you run enroll --project ABS_PROJECT --root ABS_ROOT
--session ACTUAL_SESSION_ID --days DAYS --yes. Do not infer authorization to
enroll a whole project or mixed production directory from a generic cleanup
request. Default retention is seven days; --days 0 requires the user's intent
to make newly observed files immediately eligible. Enrollment never adopts
old files or changes auto mode. Git trees remain protected; use external
scratch for Git projects. Unenroll --root ABS_ROOT --yes withdraws the policy
without moving files; old plans lose authorization.

Status reports project_scratch and project_scratch_errors. Each enrollment binds
a root identity to one session; changed/missing roots fail closed and remain
removable via unenroll. Matching Pre/Post snapshots cover at most 2000 combined
entries per phase. Overflow, access failures, overlapping turns or legacy pending
calls disable dynamic coverage and record coverage-skipped; literal creation
evidence remains usable. Do not describe all creations as tracked without
checking status. Existing project files can be listed as review candidates, but
never retroactively manufacture Hook tracking records for them.


When the task used host image generation, review the other output location too:
run generated-preview --session ACTUAL_UUID --copy-root ABS_ARCHIVE to compare
CODEX_HOME/generated_images/that-session against explicitly saved project images.
Repeat copy-root when necessary; never scan all generated_images sessions or
all Codex data. The command is read-only and creates no state, tracking or
executable plan. A verified duplicate is a review candidate, not disposal
authorization: its original path may still be used by the conversation or image
edits. No match means no backup verified. Keep source copies outside Codex home.
Do not enroll generated_images as project scratch or fabricate creation evidence
for existing host images.
