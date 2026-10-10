# Development

Use Python 3.10+ and the standard library for the runtime. Keep all user state
outside the package. Never test cleanup against actual home, Codex data, or
project files. Use temporary fixtures with an isolated `--data` directory.

Cleanup must fail closed: no filename-only ownership, no recursive deletion,
no symlinks/reparse points, no Git trees, no hardlinks, no automatic permanent
deletion, and no maintenance without explicit root enrollment. Preview and
execution must revalidate current policy and file identity. Do not claim host
support or stability without corresponding evidence.

Before publishing, run `python3 -m unittest discover -s tests -v` and
`python3 tools/package.py --check`. Add regression tests for changed safety
boundaries. Keep Chinese and English documentation consistent.
