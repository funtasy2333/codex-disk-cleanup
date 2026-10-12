# Validation

Version: 0.1.2. Research/development dates: 2026-10-10–11.

## v0.1.3 candidate — 2026-10-12

Native v0.1.2 acceptance in session
`01a12dcb-b27c-73e1-af03-877c2866a8a0` proved actual creation tracking via the
normal editor and PreToolUse/PostToolUse. The 38-byte `test_preview_native.py`
remained tracked and present, but the session-scoped quick dry-run returned
empty items and zero bytes. Its tool call held a live pending lease, which
caused plan() to skip the whole session. No apply, purge or policy change was
performed during that acceptance.

Candidate 0.1.3 separates preview visibility from execution eligibility:

- Manual previews and preview-mode lifecycle plans can display busy snapshots
  with a `blocked` reason; automatic quarantine and move() keep pending guards.
- `status` groups live pending tools without mutating leases. Schema 1 and
  native hook definitions are unchanged.
- Eleven new isolated regressions cover the CLI under a matching pending Hook
  fixture, exact path/bytes/plan ID, preview preservation, refusal to apply while
  busy, normal completion and expiry, modified fingerprints, session/turn and
  retention filters, lifecycle modes, and read-only pending diagnostics.
- The CLI fixture test reproduced empty candidates against 0.1.2 before the
  implementation change. All 82 cases pass locally on macOS / Python 3.11.4;
  package checks pass. All cleanup operations in these tests use isolated
  temporary data and files, never actual user scratch or caches.

These are unit/subprocess fixture results, not new native dispatch acceptance.
The active desktop remains on 0.1.2. Candidate 0.1.3 has not yet been published,
installed, tested in the CI matrix, or accepted for native Stop/SessionEnd.
Its pending guard intentionally remains strict: an apply command invoked as a
native tool can block itself; it must not bypass a lease to perform a move.

## Local evidence

- 71 unittest cases passed on macOS / Python 3.11.4.
- Separate hook processes exercised SQLite concurrency (six simultaneous posts).
- Tests exercise preexisting-file preservation, exact call/session identity,
  protected paths, Git trees, links, modified fingerprints, replay/expiry,
  retention, pending tools, active leases, preview mode, quarantine, restore,
  purge confirmation, maintenance enrollment and crash recovery.
- Legacy-only installable manifest, hook references, skill presence,
  marketplace path and deterministic package structure are checked by
  `python tools/package.py --check`.
- The portable example passed the Agent Plugins 1.0 JSON Schema in v0.1.0,
  but native inspection proved this format does not register its hooks. v0.1.1
  distributes only `.codex-plugin/plugin.json`.
- Codex CLI `0.162.0-alpha.17.2` discovered the package at version 0.1.0 via
  `plugin list --available --json` with a command-local marketplace override.
  Installation was subsequently confirmed, but native APIs returned zero hooks.
  Native `plugin/read` now parses five hooks from the corrected v0.1.1 source.
- Nine new regressions cover host data allocation, manifest identity, precedence,
  missing-state read-only status, existing-state queries and rejected schema.
- Tests use isolated temporary fixtures. No real user cache/log/scratch data
  is cleaned during development.

## Continuous integration

Runtime commit `340165fb703c1cf551f050822f146e4453327121` passed all six matrix jobs:
[run 38060756527](https://github.com/funtasy2333/codex-disk-cleanup/actions/runs/38060756527).
Each job ran 62 tests plus package checks and ZIP generation. This establishes
cross-platform fixture behavior, not desktop-native hook dispatch acceptance.

`.github/workflows/ci.yml` runs the same suite on `ubuntu-latest`, `macos-latest`,
and `windows-latest`, Python 3.10 and 3.13. Current results must be read from
[GitHub Actions](https://github.com/funtasy2333/codex-disk-cleanup/actions/workflows/ci.yml),
not inferred from the presence of the workflow file. Symlink tests may skip on
Windows when the runner cannot create symlinks.

The first CI run exposed an SQLite connection retained when an unsupported
schema was rejected on Windows/Python 3.13. The rejection now explicitly closes
the connection. Follow-up changes also guard pathless/in-place pending tools
and make `dry-run --apply` invalid at the argument parser.

## v0.1.1 acceptance

Runtime commit `02b5ef436ab2bef2e860bff19bfcb44261d93a15` passed all six matrix
jobs, each with 71 tests and packaging checks:
[run 38114505816](https://github.com/funtasy2333/codex-disk-cleanup/actions/runs/38114505816).

The user's local CLI `0.162.0-alpha.17.2` was upgraded through supported config
and plugin commands to pinned v0.1.1. Seven installed package files exactly match
release source. Native `plugin/read` returns five hooks; native `hooks/list`
returns all five enabled, each `trustStatus: untrusted`, with no load errors.
There is one host warning: SessionEnd timeout is clamped from 15 to 3 seconds.
This host limit is respected; recovery and the next SessionStart handle interrupted
operations. Native dispatch and actual timeout behavior remain unverified.

Running the installed script's `status` without environment or `--data` resolves
`CODEX_HOME/plugins/data/codex-disk-cleanup-codex-disk-cleanup-marketplace`, with
`data_source: codex-installation`, `initialized: false`, `hooks_seen: false`,
`auto: preview`. No cleanup database was created and no user files were cleaned.
Trust and native dispatch remain distinct checks.

## v0.1.2 acceptance

SessionEnd now explicitly uses the native 3-second maximum, with the package
validator enforcing that value. Other Hook timeouts remain 15 seconds.
Runtime commit `3e6fe380cfc1969d6f8e416bcbf9267707a13279` passed all six CI
matrix jobs, each running 71 tests and package checks:
[run 38114858264](https://github.com/funtasy2333/codex-disk-cleanup/actions/runs/38114858264).

After restarting the desktop, CLI discovery confirms installed/enabled v0.1.2,
the marketplace remains pinned to v0.1.2, and all seven installed files match
release source. Native `hooks/list` returns all five hooks enabled and trusted,
with `errors: []` and `warnings: []`; SessionEnd has `timeoutSec: 3`.
The real resumed conversation received SessionStart's scratch/state context.
Installed status reports `initialized: true`, `hooks_seen: true`, `auto: preview`,
with no tracked or quarantined files and no maintenance roots. Hook observation
alone does not prove all five events or full lifecycle cleanup behavior.

Status in the restricted tool sandbox could not open the existing SQLite WAL
state. The same read-only command succeeded with host filesystem permission;
no cleanup or policy change was performed.

Updating the marketplace while this chat was active removed its referenced
v0.1.1 cache. Its old PreToolUse and Stop commands then failed with missing-file
errors, interrupting verification and causing repeated Stop prompts. Restarting
loaded the already-installed v0.1.2 and restored command execution. Future
upgrades should be done after stopping active chats, then restarting the desktop;
never modify cached scripts or trust records as a workaround.

## Remaining acceptance

Long-term production reliability is not established by these tests. Complete
native lifecycle dispatch, cleanup behavior and Windows desktop behavior still
need user-environment acceptance.
Payload fixtures are not proof of dispatch by every host version. No support is
claimed for cloud-orchestrated Work, network filesystems or hostile concurrent
filesystem mutation. Release 0.1.2 starts in preview mode.
