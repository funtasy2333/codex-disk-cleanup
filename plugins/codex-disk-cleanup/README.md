# Codex Disk Cleanup 0.1.2

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

Explicitly enable automatic quarantine with `init --auto quarantine`; return to
preview with `init --auto preview`. Auto mode only handles newly proven scratch
files, never maintenance roots. `test_*` files can be moved at Stop. Keep permanent
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
