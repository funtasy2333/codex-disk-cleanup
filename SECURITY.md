# Security and data boundaries

This plugin performs local filesystem maintenance. It sends no file contents,
paths or audit records to a server. GitHub CI only uses isolated test fixtures.
State and audit records contain local paths, fingerprints and session IDs;
protect the data directory using OS permissions and do not commit it.

## Enforced protections

- Only builtin per-session scratch and explicitly enrolled, session-bound project
  scratch can be tracked. Matching pre/post calls observe new paths using literal
  arguments or bounded directory snapshots; there is no output-based discovery.
  Enrollment does not adopt existing files or change auto mode. A project root
  must remain a dedicated strict subdirectory with the enrolled device/inode.
  Withdrawal invalidates plans; project retention overrides filename categories.
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
- Runtime-handled errors skip cleanup. Missing installed Hook scripts or native
  host timeouts can still block tool dispatch; upgrade after stopping active
  chats and restart instead of editing installed caches or trust records.

generated-preview is a separate read-only exception for one explicitly selected
CODEX_HOME/generated_images/UUID directory. It compares fingerprints against
explicit archive directories outside Codex home, creates no state or tracking,
and offers no executable plan. It does not authorize moving conversation image
sources merely because identical copies were observed.

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
maintenance. File size (64 MiB), snapshot budget (2000 combined entries per
phase, across at most 16 project roots) and hook timeout (15 s)
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

## Observed system-temporary roots (0.1.5 candidate)

The user's requested discovery policy authorizes future observed dedicated
OS-temp subdirectories, not a whole-temp maintenance scan. Missing-path evidence
and stable existing-parent/base/root identities are required across matching
call/session/turn events. Discovery records are bounded and separate from user
configuration. Initial contents and outside project paths are review-only metadata;
they never confer deletion rights. Existing/shared roots, output-only references,
links, Git and protected data remain excluded.

Observed foreign-session access prevents moves and overlapping creation adoption.
This is advisory Hook evidence, not a process-level filesystem watcher or hostile
concurrency sandbox; references absent from inputs/cwd cannot be attributed. The
24-hour lease and existing fingerprint/race limits still apply. Disable revokes
new moves; forgetting refuses unresolved quarantine. No automatic permanent or
recursive deletion, no retroactive real-user directory adoption.

Withdrawal's quarantine guard and metadata deletion share an immediate SQLite
transaction, preventing a concurrent move from losing restore authority. Explicit
project enrollment rejects overlap with persisted discovered roots. Execution
rechecks the on-disk discovery switch; another process can revoke old plans.
Review-only observations exclude Codex home (including a custom CODEX_HOME) and
plugin state. Oversized literal inputs are not silently truncated: an unknown
access lease blocks every move and invalidates concurrent creation evidence.
