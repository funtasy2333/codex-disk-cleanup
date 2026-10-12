# Changelog

## 0.1.4 — 2026-10-12

- Add explicit per-session enrollment of dedicated project scratch directories,
  with root identity, retention and overlap checks; withdrawal invalidates plans.
- Observe dynamic Python/shell file paths through bounded pre/post directory
  snapshots in managed roots. Existing files are not adopted; unsafe/ambiguous
  or over-budget snapshots fail closed and report coverage-skipped.
- Keep schema 1 and read legacy pending lists. Preview, pending guards, path and
  fingerprint checks, quarantine/restore and explicit purge remain in force.
- Improve SessionStart file-location guidance and root/status diagnostics.
- Add a separate read-only generated-preview command for exact per-session host
  image directories and SHA-256 matching archive copies. It creates no state,
  tracking or executable plans and never cleans conversation image sources.
- Add 51 isolated project-root, dynamic subprocess, generated-image preview and
  safety regressions, including protected-source rename and cross-root overflow
  ownership checks. Read fresh lstat identities rather than Windows DirEntry
  placeholder zeros. Full native lifecycle acceptance remains outstanding.

## 0.1.3 — 2026-10-12

- Fix manual previews omitting a tracked file when the preview command itself
  has a native PreToolUse pending lease. Candidate snapshots retain path,
  fingerprint, bytes and plan ID; `blocked` explains pending execution guards.
- Separate preview visibility from permission to move. Apply and automatic
  quarantine still refuse any session with a live pending tool. No leases are
  ignored, deleted or forged to make a command pass.
- Preview-mode lifecycle events can show blocked candidates; quarantine-mode
  events report pending skips. Session, turn, retention and fingerprint checks
  remain in force. Byte totals include blocked candidates.
- Add read-only `pending_sessions` diagnostics and 11 regression cases using
  isolated fixtures. No schema, existing policy or native hook definition change.

## 0.1.2 — 2026-10-11

- Set SessionEnd timeout to the native 3-second maximum, removing the loader
  clamp warning shown in Settings → Hooks. Other events retain 15 seconds.
- Enforce event-specific timeout limits during package checks.
- Keep preview mode, retention rules and existing state unchanged.

## 0.1.1 — 2026-10-11

- Fix native hook registration: distribute only the Codex legacy manifest;
  move the root portable manifest to a documentation example outside the package.
- Resolve the installed data allocation from verified native cache identity when
  ordinary tools do not inherit `PLUGIN_DATA`.
- Make status read-only and expose initialization and observed hook state.
- Add nine regression cases for packaging, identity, state resolution and status.
- Normalize ZIP platform metadata for reproducible cross-platform packages.

## 0.1.0 — 2026-10-10

Initial testable local plugin release.

- Per-session scratch directories and matching pre/post creation evidence.
- SessionStart, PreToolUse, PostToolUse, Stop and SessionEnd adapters.
- Preview default; optional automatic quarantine with retention and pending guards.
- Explicit cache/log enrollment and manual maintenance previews.
- Single-use plans, fingerprint revalidation, restore and explicit purge.
- SQLite concurrency, operation intents, recovery and bounded audit records.
- Portable and Codex compatibility manifests, Git marketplace and ZIP packaging.
- Safety regression suite and Linux/macOS/Windows CI matrix.
