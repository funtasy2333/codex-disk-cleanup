# Review candidates to reversible quarantine

User approved the presented six-stage workflow and requested implementation.
Proceed inline without repeated approval of the same scope. This source change
is not permission to process live candidates or publish/install a new release.
Baseline: v0.1.5 / 47aac898; stdlib Python3.10+, schema1 optional tables.

Flow: review-list shows exact path, size, observation source, manually supplied
purpose, choice, current identity and a snapshot token. Unexplained use is shown
as unknown, never inferred as disposable. review-mark binds keep/quarantine and
nonempty purpose to one candidate/session and the freshly displayed token.
Changed/missing/unsafe files cannot reuse a stale snapshot. Quarantine marking
pins a content hash and immediate parent identity; keep marks block automatic
moves for that path. No automatic candidate adoption or review execution.

review-plan creates a 15-minute single-use exact list of marked quarantine
files, optional explicit candidate subset, total bytes and SHA256 list digest.
review-apply PLAN --digest DIGEST --yes confirms that exact list. Normal apply
cannot bypass review confirmation. Revalidate choice token, observation record,
parent identity, file fingerprint, all path protections and pending access.
Mixed delivery/project directories authorize only named files, never a root
scan or neighboring files. Explicit review confirmation permits immediate manual
quarantine without changing automatic retention or configuration.

Same-parent quarantine reuses durable moves and existing restore/purge/recover.
An optional per-move approval archive preserves exact source/parent authority
independently of later candidate eviction/choice changes/discovery disable.
Restore never overwrites and retains the restored path. Pending records now
retain bounded full literal/cwd access metadata; legacy incomplete access blocks
manual review moves. Matching owner-session and foreign parent access block.
No new permanent deletion, recursive deletion, protected/Git/link/hardlink bypass,
CODEX_HOME/generated_images cleanup, or mutation of live plugin state in tests.

Verify isolated happy flow and CLI, missing/wrong selection/confirmation,
file/parent replacement, stale and reused plans, choice revocation, read-only
old state, pending/legacy/foreign/overflow protection, mixed-directory neighbors,
restore/purge/recovery and durable authorization after queue eviction. Update
Chinese/English guides, skill workflow and version0.1.6. Final independent review,
complete regression suite, reproducible package/source checks and candidate export.
