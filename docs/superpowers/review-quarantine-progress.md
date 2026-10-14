# Review-quarantine execution record

Baseline: v0.1.5/47aac898 with 182 tests. User approved the six-stage workflow and
asked to implement it. Inline implementation; no renewed approval gate for the
same scope, no real-candidate processing or release/install inferred.

Initial 37 isolated missing-feature tests ran red before runtime changes.
Implemented metadata-only list, snapshot+purpose marking, keep veto, exact subset
plan and digest confirmation, per-file parent authority, archived restore/recover.
Additional before-fix failures proved display-to-hash race, temp alias/missing cwd
pending guards and eviction-safe restored keep. Final: 48 new tests, 230 total.

Independent reviewer reproduced and verified resolution of temp aliases, missing
cwd, missing restore keep and identity display. Full suite independently rerun.
All fixtures are temporary; no live candidate was marked/moved. Documentation
explains purpose honesty, no automatic adoption, exact-file confirmation, pending
limits, new runtime needed for review-move restoration and current installed1.5.

Source candidate0.1.6 stays on feat/review-quarantine. Plugin/source ZIPs, baseline
patch, test evidence and checksums are exported under task outputs. Native lifecycle
and cross-platform CI are separate acceptance stages; no publication/installation.

Skill/reference pressure check: old1.5 guide lacked a supported approval bridge;
new guide produced the exact render-only plan, retained the source and unknown
item, refused silent snapshot refresh and lease bypass, and did not broaden
implementation authorization to all61 candidates. Clarified that lifecycle cleanup
cannot execute manual review plans; full CLI flow remains verified by subprocess.
