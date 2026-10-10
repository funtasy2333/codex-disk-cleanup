# Security and data boundaries

This plugin performs local filesystem maintenance. It sends no file contents,
paths or audit records to a server. GitHub CI only uses isolated test fixtures.
State and audit records contain local paths, fingerprints and session IDs;
protect the data directory using OS permissions and do not commit it.

## Enforced protections

- Only per-session managed scratch paths can be automatically tracked. The exact
  session and call must observe absence before creation; no output-based discovery.
- Maintenance requires explicit paths inside `CODEX_HOME/cache` or `CODEX_HOME/logs`.
  It never runs automatically. Current policy must still match a preview.
- Git trees, secrets/control files, sessions, memories, skills, plugins,
  deliverables, databases, private keys, links, junctions/reparse points and
  multiple-link files are rejected. Directories are never deletion candidates.
- Files modified after tracking/preview are skipped. Metadata and SHA-256 are
  rechecked before movement. Plans expire and are single-use.
- Default automatic mode is preview. Apply moves files within their source root
  to quarantine. Permanent deletion requires a selected quarantine ID and `--yes`.
- SQLite transactions serialize state mutations. Durable move/restore/purge
  intents can be reconciled with `recover`. Ambiguity never triggers deletion.
- Hook errors skip cleanup and allow the user's original task to continue.

## Threat model and limits

The state directory, configuration and enrolled roots must be controlled by the
same trusted user on a local filesystem. SQLite/JSON state is not a security
boundary against tampering by a process running as that user. Fingerprint and
path checks reduce ordinary races; the implementation is **not** an adversarial
TOCTOU defense. A hostile process can replace directory entries between checks
and filesystem calls, especially on Windows. Do not enroll shared or hostile
directories. Same-root rename is used; no network/NFS guarantees are claimed.

An active scratch session is a 24-hour lease refreshed by hooks. A command that
runs longer than that without hooks can become stale. The pending-tool guard is
also lease-based. Keep preview mode for long-running or externally modified
workloads. Hook creation evidence does not prove causal ownership against
another process independently creating the exact same path.

POSIX allows moving open files; this plugin cannot prove that an old log/cache
file is unused by an unrelated application. Close writers before manual deep
maintenance. File size (64 MiB), scan size (2000 files) and hook timeout (15 s)
bound normal work, but hooks are advisory, and a timeout can leave an intent
requiring `recover`. Unsupported paths are skipped, not broadened automatically.

Audits retain the latest 10000 entries. Tracking/quarantine records remain until
handled; the plugin does not automatically vacuum its database, prune unknown
scratch files or purge its quarantine. Quarantine retains disk usage by design.

## Reporting

For suspected data loss or security defects, disable automatic mode (`init
--auto preview`), retain state/quarantine, and use GitHub's private vulnerability
reporting if available. Do not publish authentication files or private local
paths in public issues. Ordinary non-sensitive bugs can be reported in issues.
