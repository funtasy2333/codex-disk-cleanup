# Sources and licensing

Research date: 2026-10-10.

- Hermes Agent `plugins/disk-cleanup` at commit
  [`f925b01791fe052e7d55dc975750c0bd985aff91`](https://github.com/NousResearch/hermes-agent/tree/f925b01791fe052e7d55dc975750c0bd985aff91/plugins/disk-cleanup).
  Reviewed `disk_cleanup.py` and `__init__.py` for creation evidence, safe path
  checks, retention and Git protection. MIT license, Nous Research. This project
  is an independent implementation, not a verbatim copy or endorsement.
- [Official Codex Hooks](https://learn.chatgpt.com/docs/hooks): event names,
  stdin fields, call IDs, JSON output, `commandWindows`, plugin environment,
  trust and cloud-orchestration limits.
- [Official plugin packaging](https://developers.openai.com/plugins/build/plugins):
  root Agent Plugins manifest, OpenAI extension, compatibility overlay,
  marketplace format, relative source and bundled hook paths.
- [Hook distribution limits](https://developers.openai.com/plugins/guides/submit-claude-plugin):
  manual distribution for hook-dependent desktop plugins.

The runtime has no third-party Python dependencies. MIT license is included at
repository and plugin roots, including acknowledgement of the upstream design.
