# Validation

Version: 0.1.0. Research/development date: 2026-10-10.

## Local evidence

- 58 unittest cases passed on macOS / Python 3.11.4.
- Separate hook processes exercised SQLite concurrency (six simultaneous posts).
- Tests exercise preexisting-file preservation, exact call/session identity,
  protected paths, Git trees, links, modified fingerprints, replay/expiry,
  retention, pending tools, active leases, preview mode, quarantine, restore,
  purge confirmation, maintenance enrollment and crash recovery.
- Portable/compatibility manifest consistency, hook references, skill presence,
  marketplace path and deterministic package structure are checked by
  `python tools/package.py --check`.
- Tests use isolated temporary fixtures. No real user cache/log/scratch data
  is cleaned during development.

## Continuous integration

`.github/workflows/ci.yml` runs the same suite on `ubuntu-latest`, `macos-latest`,
and `windows-latest`, Python 3.10 and 3.13. Current results must be read from
[GitHub Actions](https://github.com/funtasy2333/codex-disk-cleanup/actions/workflows/ci.yml),
not inferred from the presence of the workflow file. Symlink tests may skip on
Windows when the runner cannot create symlinks.

## Remaining acceptance

Long-term production reliability is not established by these tests. Desktop
installation, the user's hook trust review, new-chat context, actual native
hook dispatch and Windows desktop behavior need user-environment acceptance.
Payload fixtures are not proof of dispatch by every host version. No support is
claimed for cloud-orchestrated Work, network filesystems or hostile concurrent
filesystem mutation. Release 0.1.0 should start in preview mode.
