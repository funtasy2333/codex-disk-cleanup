# Changelog

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
