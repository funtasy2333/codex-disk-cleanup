# Automatic session temporary-directory discovery

Approved direction: the user asked to implement the in-chat design directly. Ordinary conversations need not change file locations to use scratch. The existing scratch remains an optional managed location. No public release, installed-cache replacement, enrollment of historical real directories or actual cleanup is requested in this turn.

## Discovery and identity
Use literal paths in structured tool inputs, shell tokens and quoted path strings without evaluating code or parsing tool output. Consider only paths under canonical system temporary bases (stdlib tempfile.gettempdir, and /tmp on POSIX); do not walk a whole base. Pre records the first missing directory candidate beneath an existing safe parent and pins the parent's dev/inode. Post must match session/call/turn, find a safe directory and revalidate parent/base identities. Existing directories, links, Git trees, protected names, broad roots, Codex data, overlapping managed roots, mismatched/ambiguous events cannot confer ownership; failed calls cannot confer file ownership. At most16 discovered roots per session and2000 total persisted roots.

Persist root identity/session/7-day retention separately from user config. Files present when the directory is first discovered are review candidates only, never adopted. Later matched Pre/Post bounded snapshots reuse the existing identity/pending/retention machinery. Any incomplete or ambiguous phase suspends adoption. Root replacement, configuration disable or forget invalidates move plans. Retention stays seven days even for test_* in discovered roots. Quarantine stays inside each root; restoration checks identity and cannot overwrite. No directory or automatic permanent deletion.

## Observations and compatibility
Literal outside-managed file paths absent before and safely inspected with metadata after matching calls can become bounded review-only observations; protected/Git/Codex paths remain excluded. They do not read or hash contents and create no executable plan or deletion permission. This covers explicit project output paths, not arbitrary code or a full filesystem inventory. generated-preview remains the separate read-only source-image comparison mechanism. No retroactive adoption of existing historical temporary directories.

Schema1 remains backward-readable by older runtimes: optional discovered_temp and review_candidates tables. Read-only status on older data without these tables returns empty discovery/observation lists. Expose discoveries/errors and reviewed candidates. Configuration discover_temp defaults true for future calls; an explicit boolean false disables discovery and new moves without changing auto. forget-temp --root ABS --yes removes metadata only and refuses unresolved quarantine until restore/purge/recovery is settled. init --discover-temp on|off preserves existing roots/policy.

## Verification
Use only TemporaryDirectory fixtures. Prove normal dynamic generation in a freshly discovered directory, first-call content preservation, seven-day eligibility, plans/pending/root-identity/restore/forget/disable behavior, bounds and ambiguity, protected-source rename and cross-root moves, alias safety, old-state read-only compatibility, and actual CLI/Python subprocess generation. Update Chinese/English documentation, optional SessionStart guidance and version0.1.5 package checks. Perform independent final review. Native desktop dispatch, cross-platform CI and release/install are separate acceptance stages.

Foreign-session explicit temporary-root/cwd access blocks moves and invalidates overlapping creation evidence on both calls, even when the foreign writer finishes first. Initial failed calls may bind observed directories but cannot own their contents.

Unknown access from oversized literal input keeps a blocking pending lease and
invalidates concurrent creation evidence. Forget's move guard and metadata removal
are atomic; enrollment cannot shadow a discovered root. Execution reads current
discovery configuration, and observations exclude custom Codex home/plugin state.
