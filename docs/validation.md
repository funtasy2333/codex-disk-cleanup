# Validation

Version: 0.1.1. Research/development dates: 2026-10-10–11.

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

Local tests and package checks passed. Native source-package hook parsing passed.
Installed hook registry verification and the v0.1.1 CI result will be recorded
after publishing and upgrading. Trust and dispatch remain distinct checks.

## Remaining acceptance

Long-term production reliability is not established by these tests. Desktop
installation, the user's hook trust review, new-chat context, actual native
hook dispatch and Windows desktop behavior need user-environment acceptance.
Payload fixtures are not proof of dispatch by every host version. No support is
claimed for cloud-orchestrated Work, network filesystems or hostile concurrent
filesystem mutation. Release 0.1.1 starts in preview mode.
