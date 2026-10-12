# Automatic temporary-directory discovery Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. The user explicitly requested direct implementation; preserve the approved design and do not ask for repeated artifact approvals.

**Goal:** Track temporary files at the locations conversations actually choose.
**Architecture:** Match Pre/Post events, discover only referenced new system-temp directories, pin root identity, reuse existing snapshots and execution checks. Keep outside observations separate from cleanup ownership.
**Tech Stack:** Python3.10+, standard library, SQLite schema1 optional tables.
**Spec:** docs/superpowers/specs/2026-10-12-auto-temp-discovery.md

## Global Constraints
- Runtime standard library only; all state outside package; tests use isolated temporary fixtures.
- No old-file adoption, links, Git, broad scans, recursive deletion or auto permanent deletion.
-16 discovered roots/session;2000 total roots and bounded review observations; seven-day discovered-root retention.
- No publish, install or real-directory cleanup during this source change.

## Review Focus
- Existing temp roots and first-call contents must never become cleanup-owned.
- Parent/root replacement and disabled policy must invalidate executable plans.
- Concurrent/cross-turn evidence must fail closed without borrowing another call's root.
- Protected originals renamed/moved across managed roots must remain untouched.
- Legacy schema1 read-only status must work without new tables.

### Task1: Implement discovery and review-only observation state
Files: scripts/cleanup.py, tests/test_temp_discovery.py.
Interfaces: Store.temporary_bases, temp_candidates(payload), validate_temp_root(spec), managed_roots(session), status discovery/observation fields.
- [ ] Add failing discovery/first-call/old-directory/alias/protected/ambiguity/limits/old-state tests.
- [ ] Run and inspect expected failures.
- [ ] Add optional state tables and discovery helpers; integrate matched Hooks with stable identity and bounded observations.
- [ ] Add lifecycle/retention/root-change/disable/forget/restore and actual subprocess failing tests; run red then implement plan/root/execution checks.
- [ ] Run complete unittest suite and commit.

### Task2: Document and package candidate
Files: runtime version, manifest, config example, SKILL, README Chinese+English, CHANGELOG, SECURITY, design and validation.
- [ ] Make SessionStart scratch guidance optional and document exact automatic coverage limits.
- [ ] Run unittest, package --check, git diff --check; build deterministic package.
- [ ] Commit and independent whole-branch review; resolve important findings with red-green regressions.
- [ ] Export source/patch/package/verification and retain the branch for user review.
