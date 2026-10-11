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

## Native compatibility correction (2026-10-11)

Codex CLI `0.162.0-alpha.17.2` installed/enabled v0.1.0 and loaded its Skill, but
native `plugin/read` returned zero hooks and `hooks/list` omitted this plugin.
The root portable manifest took precedence over the compatibility overlay.
The native loader deliberately skips hooks for `PluginManifestFormat::AgentPlugin`:
[loader.rs](https://github.com/openai/codex/blob/cc7ba33601286a751477832b01de7b6f8de0dd9c/codex-rs/core-plugins/src/loader.rs).
The same API parses all five hooks from the corrected legacy-only source package.
This source/runtime evidence takes precedence over the broader packaging docs
for this release. The portable manifest is retained only as an example.

Native data allocation is `CODEX_HOME/plugins/data/<plugin-name>-<marketplace-name>`:
[PluginStore::plugin_data_root](https://github.com/openai/codex/blob/cc7ba33601286a751477832b01de7b6f8de0dd9c/codex-rs/core-plugins/src/store.rs).
The fallback resolver uses this rule only after verifying the native cache layout
and matching installed manifest. Missing state stays missing during status.
