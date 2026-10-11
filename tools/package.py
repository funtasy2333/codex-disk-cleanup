#!/usr/bin/env python3
"""Validate the package and create a reproducible plugin-only ZIP."""
import argparse
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/codex-disk-cleanup'


def check():
    legacy = json.loads((PLUGIN / '.codex-plugin/plugin.json').read_text(encoding='utf-8'))
    assert not (PLUGIN / 'plugin.json').exists(), 'Native loader skips hooks for AgentPlugin format'
    assert legacy['name'] == PLUGIN.name
    assert re.fullmatch(r'\d+\.\d+\.\d+', legacy['version'])
    assert len(legacy['interface']['shortDescription']) <= 30
    assert legacy['hooks'] == './hooks/hooks.json'
    script = (PLUGIN / 'scripts/cleanup.py').read_text(encoding='utf-8')
    assert f'VERSION = "{legacy["version"]}"' in script
    hooks = json.loads((PLUGIN / 'hooks/hooks.json').read_text(encoding='utf-8'))['hooks']
    assert set(hooks) == {'SessionStart', 'PreToolUse', 'PostToolUse', 'Stop', 'SessionEnd'}
    for event, groups in hooks.items():
        for group in groups:
            for handler in group['hooks']:
                assert handler['type'] == 'command'
                assert '${PLUGIN_ROOT}/scripts/cleanup.py' in handler['command']
                assert '${PLUGIN_ROOT}/scripts/cleanup.py' in handler['commandWindows']
                assert handler['timeout'] == (3 if event == 'SessionEnd' else 15), (
                    'SessionEnd must respect the native 3-second limit')
    assert 'name: disk-cleanup' in (PLUGIN / 'skills/disk-cleanup/SKILL.md').read_text(encoding='utf-8')
    assert (PLUGIN / 'scripts/cleanup.py').is_file()
    assert (PLUGIN / 'LICENSE').is_file()
    marketplace = json.loads((ROOT / '.agents/plugins/marketplace.json').read_text(encoding='utf-8'))
    assert (ROOT / marketplace['plugins'][0]['source']['path']).resolve() == PLUGIN
    return legacy['version']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    version = check()
    if args.check:
        print('Package checks passed')
        return
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    target = dist / f'codex-disk-cleanup-{version}.zip'
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PLUGIN.rglob('*')):
            if path.is_symlink():
                raise ValueError(f'Symlink in package: {path}')
            if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
                continue
            info = zipfile.ZipInfo('codex-disk-cleanup/' + path.relative_to(PLUGIN).as_posix(),
                                   date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    print(target)


if __name__ == '__main__':
    main()
