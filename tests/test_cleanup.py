import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

SCRIPT = Path(__file__).resolve().parents[1] / 'plugins/codex-disk-cleanup/scripts/cleanup.py'
spec = importlib.util.spec_from_file_location('cleanup', SCRIPT)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.store = c.Store(self.base / 'data')
        self.root = self.store.workspace('s1')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def payload(self, event, path=None, session='s1', call='c1', turn='t1', **extra):
        p = {'hook_event_name': event, 'session_id': session, 'cwd': str(self.base),
             'turn_id': turn, 'tool_use_id': call, 'tool_name': 'Write',
             'tool_input': {'path': str(path or self.root / 'test_a.py')}}
        p.update(extra)
        return p

    def create(self, name='test_a.py', session='s1', call='c1', turn='t1'):
        root = self.store.workspace(session)
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        self.store.hook(self.payload('PreToolUse', path, session, call, turn))
        path.write_text('temporary contents', encoding='utf-8')
        self.store.hook(self.payload('PostToolUse', path, session, call, turn))
        return path

    def plan(self):
        return self.store.plan(session='s1')

    def move(self, path=None):
        path = path or self.create()
        plan = self.plan()
        result = self.store.apply(plan['plan_id'])
        self.assertEqual(len(result['quarantined']), 1, result)
        return path, result['quarantined'][0]

    def test_default_is_preview(self):
        self.assertEqual(self.store.config['auto'], 'preview')
        path = self.create()
        self.store.hook(self.payload('Stop'))
        self.assertTrue(path.exists())

    def test_track_proven_new_file(self):
        path = self.create()
        self.assertEqual(self.store.status()['tracked'][0]['path'], str(path))

    def test_preexisting_file_not_tracked(self):
        path = self.root / 'test_existing.py'
        path.write_text('permanent')
        self.store.hook(self.payload('PreToolUse', path))
        path.write_text('edited')
        self.store.hook(self.payload('PostToolUse', path))
        self.assertEqual(self.store.status()['tracked'], [])

    def test_post_without_pre_not_tracked(self):
        path = self.root / 'test_existing.py'
        path.write_text('exists')
        self.store.hook(self.payload('PostToolUse', path))
        self.assertEqual(self.store.status()['tracked'], [])

    def test_call_identity_must_match(self):
        path = self.root / 'test_a.py'
        self.store.hook(self.payload('PreToolUse', path, call='first'))
        path.write_text('exists')
        self.store.hook(self.payload('PostToolUse', path, call='different'))
        self.assertEqual(self.store.status()['tracked'], [])

    def test_session_identity_must_match(self):
        path = self.root / 'test_a.py'
        self.store.hook(self.payload('PreToolUse', path))
        path.write_text('exists')
        self.store.hook(self.payload('PostToolUse', path, session='s2'))
        self.assertEqual(self.store.status()['tracked'], [])

    def test_paths_from_output_not_tracked(self):
        path = self.root / 'test_a.py'
        path.write_text('exists')
        p = self.payload('PostToolUse', tool_input={'command': 'ls'}, tool_response=str(path))
        self.store.hook(p)
        self.assertEqual(self.store.status()['tracked'], [])

    def test_outside_scratch_not_tracked(self):
        path = self.base / 'test_permanent.py'
        self.store.hook(self.payload('PreToolUse', path))
        path.write_text('permanent')
        self.store.hook(self.payload('PostToolUse', path))
        self.assertEqual(self.store.status()['tracked'], [])

    def test_traversal_not_tracked(self):
        path = self.root / '..' / 'test_escape.py'
        self.store.hook(self.payload('PreToolUse', path))
        path.write_text('permanent')
        self.store.hook(self.payload('PostToolUse', path))
        self.assertEqual(self.store.status()['tracked'], [])

    def test_protected_names(self):
        for name in ['outputs/test_a.py', 'skills/test_a.py', '.env', 'auth.json',
                     'AGENTS.md', 'file.sqlite3', 'x.key', '.git/test_a.py', 'config.json',
                     'state.sqlite3-wal', 'state.sqlite-shm', 'state.db-journal']:
            with self.subTest(name=name):
                with self.assertRaises(c.Refused):
                    self.store.candidate(self.root / name, self.root)

    def test_git_worktree_protected(self):
        path = self.create()
        (self.root / '.git').write_text('gitdir: other')
        self.assertEqual(self.plan()['items'], [])
        self.assertTrue(path.exists())

    def test_git_ancestor_protected(self):
        (self.base / '.git').mkdir()
        with self.assertRaises(c.Refused):
            self.store.workspace('s1')

    def test_modified_file_skipped(self):
        path = self.create()
        path.write_text('important revision')
        self.assertEqual(self.plan()['items'], [])
        self.assertTrue(path.exists())

    def test_changed_after_preview_skipped(self):
        path = self.create()
        plan = self.plan()
        path.write_text('important revision')
        result = self.store.apply(plan['plan_id'])
        self.assertEqual(result['quarantined'], [])
        self.assertTrue(path.exists())

    def test_same_size_preserved_mtime_edit_skipped(self):
        path = self.create()
        plan = self.plan()
        before = path.stat()
        path.write_text('x' * before.st_size)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(self.store.apply(plan['plan_id'])['quarantined'], [])

    def test_replaced_inode_skipped(self):
        path = self.create()
        plan = self.plan()
        contents = path.read_bytes()
        replacement = path.with_name('replacement')
        replacement.write_bytes(contents)
        os.replace(replacement, path)
        self.assertEqual(self.store.apply(plan['plan_id'])['quarantined'], [])

    def test_directory_never_deleted(self):
        p = self.root / 'test_dir'
        self.store.hook(self.payload('PreToolUse', p))
        p.mkdir()
        self.store.hook(self.payload('PostToolUse', p))
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertTrue(p.is_dir())

    def test_hardlink_rejected(self):
        path = self.create()
        os.link(path, path.with_name('second'))
        self.assertEqual(self.plan()['items'], [])

    def test_symlink_rejected(self):
        path = self.create()
        plan = self.plan()
        victim = self.base / 'victim'
        victim.write_text('important')
        path.unlink()
        try:
            path.symlink_to(victim)
        except OSError:
            self.skipTest('symlink creation unavailable')
        self.assertEqual(self.store.apply(plan['plan_id'])['quarantined'], [])
        self.assertEqual(victim.read_text(), 'important')

    def test_parent_symlink_rejected(self):
        victim_dir = self.base / 'victim-dir'
        victim_dir.mkdir()
        link = self.root / 'link'
        try:
            link.symlink_to(victim_dir, target_is_directory=True)
        except OSError:
            self.skipTest('symlink creation unavailable')
        with self.assertRaises(c.Refused):
            self.store.candidate(link / 'test_file', self.root)

    def test_large_file_rejected(self):
        path = self.root / 'test_large'
        with path.open('wb') as f:
            f.truncate(c.MAX_BYTES + 1)
        with self.assertRaises(c.Refused):
            c.fingerprint(path)

    def test_plan_replay_rejected(self):
        self.create()
        plan = self.plan()
        self.store.apply(plan['plan_id'])
        with self.assertRaises(c.Refused):
            self.store.apply(plan['plan_id'])

    def test_expired_plan_rejected(self):
        self.create()
        plan = self.plan()
        self.store.db.execute('UPDATE plans SET created=0')
        with self.assertRaises(c.Refused):
            self.store.apply(plan['plan_id'])

    def test_unknown_plan_rejected(self):
        with self.assertRaises(c.Refused):
            self.store.apply('forged')

    def test_quarantine_and_restore(self):
        path, mid = self.move()
        self.assertFalse(path.exists())
        self.store.restore(mid)
        self.assertEqual(path.read_text(), 'temporary contents')

    def test_restore_no_overwrite(self):
        path, mid = self.move()
        path.write_text('new important content')
        with self.assertRaises(c.Refused):
            self.store.restore(mid)
        self.assertEqual(path.read_text(), 'new important content')

    def test_purge_only_quarantine(self):
        path, mid = self.move()
        self.store.purge(mid)
        self.assertFalse(path.exists())
        self.assertEqual(self.store.status()['quarantine'], [])
        with self.assertRaises(c.Refused):
            self.store.purge(mid)

    def test_changed_quarantine_not_purged(self):
        path, mid = self.move()
        row = self.store.db.execute('SELECT * FROM moves WHERE id=?', (mid,)).fetchone()
        dest = Path(row['dest'])
        dest.write_text('changed')
        with self.assertRaises(c.Refused):
            self.store.purge(mid)
        self.assertTrue(dest.exists())

    def test_active_other_session_skipped(self):
        path = self.create(session='other')
        self.assertEqual(self.store.plan()['items'], [])
        self.assertEqual(self.plan()['items'], [])
        self.assertTrue(path.exists())

    def test_pending_tool_prevents_cleanup(self):
        path = self.create()
        self.store.hook(self.payload('PreToolUse', self.root / 'test_second.py', call='running'))
        self.assertEqual(self.plan()['items'], [])
        self.assertTrue(path.exists())

    def test_pending_added_after_plan_prevents_move(self):
        self.create()
        plan = self.plan()
        self.store.hook(self.payload('PreToolUse', self.root / 'test_second.py', call='running'))
        self.assertEqual(self.store.apply(plan['plan_id'])['quarantined'], [])

    def test_pending_existing_file_tool_prevents_cleanup(self):
        path = self.create()
        self.store.hook(self.payload('PreToolUse', path, call='editing'))
        self.assertEqual(self.plan()['items'], [])
        self.assertTrue(path.exists())

    def test_pending_pathless_tool_prevents_cleanup(self):
        path = self.create()
        self.store.hook(self.payload('PreToolUse', call='running', tool_input={'command': 'sleep 5'}))
        self.assertEqual(self.plan()['items'], [])
        self.assertTrue(path.exists())

    def test_stop_only_current_turn(self):
        old = self.create(call='old', turn='old')
        new = self.create('test_new.py', call='new')
        self.store.config['auto'] = 'quarantine'
        self.store.hook(self.payload('Stop'))
        self.assertTrue(old.exists())
        self.assertFalse(new.exists())

    def test_auto_session_end(self):
        path = self.create()
        self.store.config['auto'] = 'quarantine'
        self.store.hook(self.payload('SessionEnd'))
        self.assertFalse(path.exists())

    def test_stop_missing_turn_skips_cleanup(self):
        path = self.create()
        self.store.config['auto'] = 'quarantine'
        payload = self.payload('Stop')
        del payload['turn_id']
        self.store.hook(payload)
        self.assertTrue(path.exists())

    def test_session_start_skips_active_and_cleans_stale(self):
        stale = self.create(session='stale')
        active = self.create(session='active')
        self.store.db.execute("UPDATE sessions SET seen=0 WHERE id='stale'")
        self.store.config['auto'] = 'quarantine'
        self.store.hook(self.payload('SessionStart'))
        self.assertFalse(stale.exists())
        self.assertTrue(active.exists())

    def test_temp_retention(self):
        path = self.create('scratch.txt')
        self.assertEqual(self.plan()['items'], [])
        self.store.db.execute('UPDATE tracked SET created=?', (time.time() - 8 * 86400,))
        self.assertEqual(len(self.plan()['items']), 1)
        self.assertTrue(path.exists())

    def test_cron_retention(self):
        self.create('cron-output/run.txt')
        self.assertEqual(self.store.status()['tracked'][0]['category'], 'cron-output')
        self.store.db.execute('UPDATE tracked SET created=?', (time.time() - 8 * 86400,))
        self.assertEqual(self.plan()['items'], [])
        self.store.db.execute('UPDATE tracked SET created=?', (time.time() - 15 * 86400,))
        self.assertEqual(len(self.plan()['items']), 1)

    def test_literal_bash_and_patch_extraction(self):
        path = self.root / 'test_a.py'
        for command in [f'touch "{path}"', f'*** Begin Patch\n*** Add File: {path}\n+x\n*** End Patch']:
            p = self.payload('PreToolUse', tool_input={'command': command})
            self.assertIn(str(path), self.store.candidates(p, self.root))

    def test_relative_literal_path_extraction(self):
        p = self.payload('PreToolUse', tool_input={'command': 'touch test_a.py'}, cwd=str(self.root))
        self.assertIn(str(self.root / 'test_a.py'), self.store.candidates(p, self.root))

    def test_shell_not_executed(self):
        sentinel = self.base / 'sentinel'
        p = self.payload('PreToolUse', tool_input={'command': f'$(touch {sentinel})'})
        self.store.candidates(p, self.root)
        self.assertFalse(sentinel.exists())

    def test_no_maintenance_by_default(self):
        self.assertEqual(self.store.plan('deep')['items'], [])

    def enroll(self, kind='logs'):
        codex_home = self.base / 'codex-home'
        root = codex_home / kind
        root.mkdir(parents=True, exist_ok=True)
        env = patch.dict(os.environ, {'CODEX_HOME': str(codex_home)})
        env.start()
        self.addCleanup(env.stop)
        spec = {'path': str(root), 'kind': kind, 'days': 30}
        self.store.roots = [self.store.validate_root(spec)]
        self.store.config['maintenance'] = self.store.roots
        return root

    def test_maintenance_broad_roots_rejected(self):
        for root in [self.base, Path.home(), self.store.data, self.root]:
            with self.subTest(root=root):
                with self.assertRaises(c.Refused):
                    self.store.validate_root({'path': str(root), 'kind': 'cache', 'days': 30})

    def test_maintenance_retention_requires_old_ctime(self):
        root = self.enroll()
        p = root / 'old.log'
        p.write_text('log')
        os.utime(p, (0, 0))
        self.assertEqual(self.store.plan('deep')['items'], [])

    def test_maintenance_deep_only_and_revalidation(self):
        root = self.enroll()
        p = root / 'old.log'
        p.write_text('log')
        future = time.time() + 31 * 86400
        with patch.object(c.time, 'time', return_value=future):
            self.assertEqual(self.store.plan('quick')['items'], [])
            plan = self.store.plan('deep')
            self.assertEqual(len(plan['items']), 1)
            self.store.roots = []
            self.assertEqual(self.store.apply(plan['plan_id'])['quarantined'], [])
        self.assertTrue(p.exists())

    def test_maintenance_can_quarantine_restore_and_purge(self):
        root = self.enroll('cache')
        p = root / 'cache.bin'
        p.write_text('cache')
        with patch.object(c.time, 'time', return_value=time.time() + 31 * 86400):
            plan = self.store.plan('deep')
            result = self.store.apply(plan['plan_id'])
        self.assertEqual(len(result['quarantined']), 1, result)
        self.store.restore(result['quarantined'][0])
        self.assertEqual(p.read_text(), 'cache')

    def test_latest_log_and_database_protected(self):
        root = self.enroll()
        for name in ['old.log', 'auth.json', 'history.jsonl', 'state.sqlite3']:
            (root / name).write_text('x')
        with patch.object(c.time, 'time', return_value=time.time() + 31 * 86400):
            paths = [i['path'] for i in self.store.plan('deep')['items']]
        self.assertEqual(paths, [str(root / 'old.log')])

    def test_maintenance_scan_limit_fails_closed(self):
        root = self.enroll()
        (root / 'a.log').write_text('a')
        (root / 'b.log').write_text('b')
        with patch.object(c, 'MAX_ITEMS', 1), self.assertRaises(c.Refused):
            self.store.plan('deep')

    def test_recovery_after_move_before_db_finalize(self):
        path = self.create()
        fp = c.fingerprint(path)
        qdir = self.root / '.codex-disk-cleanup-quarantine'
        qdir.mkdir()
        mid = uuid.uuid4().hex
        dest = qdir / mid
        self.store.db.execute("INSERT INTO moves VALUES (?,?,?,?,?,'moving',?)",
                              (mid, str(path), str(dest), str(self.root), c.compact(fp), time.time()))
        os.rename(path, dest)
        result = self.store.recover()
        self.assertEqual(result['recovered'][0]['state'], 'quarantined')
        self.store.restore(mid)
        self.assertTrue(path.exists())

    def test_recovery_before_move(self):
        path = self.create()
        fp = c.fingerprint(path)
        mid = uuid.uuid4().hex
        dest = self.root / '.codex-disk-cleanup-quarantine' / mid
        self.store.db.execute("INSERT INTO moves VALUES (?,?,?,?,?,'moving',?)",
                              (mid, str(path), str(dest), str(self.root), c.compact(fp), time.time()))
        self.assertEqual(self.store.recover()['recovered'][0]['state'], 'cancelled')
        self.assertTrue(path.exists())

    def test_recovery_ambiguous_preserves_both(self):
        path, mid = self.move()
        row = self.store.db.execute('SELECT * FROM moves WHERE id=?', (mid,)).fetchone()
        os.link(Path(row['dest']), path)
        self.store.db.execute("UPDATE moves SET state='restoring' WHERE id=?", (mid,))
        self.assertEqual(self.store.recover()['recovered'][0]['state'], 'needs-review')
        self.assertTrue(path.exists())
        self.assertTrue(Path(row['dest']).exists())

    def test_database_schema_version_rejected(self):
        self.store.db.execute("UPDATE metadata SET value='99' WHERE key='schema'")
        with self.assertRaises(c.Refused):
            c.Store(self.store.data)

    def test_concurrent_tracking_processes(self):
        jobs = []
        for i in range(6):
            path = self.root / f'test_{i}.py'
            self.store.hook(self.payload('PreToolUse', path, call=str(i)))
            path.write_text(str(i))
            jobs.append((path, str(i)))
        processes = []
        for path, call in jobs:
            proc = subprocess.Popen([sys.executable, str(SCRIPT), '--data', str(self.store.data), 'hook'],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.stdin.write(json.dumps(self.payload('PostToolUse', path, call=call)).encode())
            proc.stdin.close()
            processes.append(proc)
        for proc in processes:
            self.assertEqual(proc.wait(timeout=20), 0)
            proc.stdout.close()
            proc.stderr.close()
        self.assertEqual(len(self.store.status()['tracked']), 6)
        self.assertEqual(self.store.status()['pending'], 0)

    def test_cli_apply_requires_yes(self):
        self.create()
        plan = self.plan()
        proc = subprocess.run([sys.executable, str(SCRIPT), '--data', str(self.store.data),
                               'quick', '--apply', plan['plan_id']], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn('--yes', proc.stderr)

    def test_dry_run_rejects_apply(self):
        path = self.create()
        plan = self.plan()
        proc = subprocess.run([sys.executable, str(SCRIPT), '--data', str(self.store.data),
                               'dry-run', '--apply', plan['plan_id'], '--yes'], capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue(path.exists())

    def test_cli_purge_requires_yes(self):
        path, mid = self.move()
        proc = subprocess.run([sys.executable, str(SCRIPT), '--data', str(self.store.data),
                               'purge', mid], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(len(self.store.status()['quarantine']), 1)

    def test_invalid_hook_json_does_not_block_tool(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), '--data', str(self.store.data), 'hook'],
                               input='{invalid', capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout), {})

    def test_missing_hook_identity_does_not_block_tool(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), '--data', str(self.store.data), 'hook'],
                               input='{}', capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout), {})

    def test_stop_stdout_valid_json(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), '--data', str(self.store.data), 'hook'],
                               input=json.dumps(self.payload('Stop')), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout), {'continue': True})

    def test_malformed_config_fails_closed(self):
        self.store.close()
        (self.store.data / 'config.json').write_text('{invalid')
        proc = subprocess.run([sys.executable, str(SCRIPT), '--data', str(self.store.data), 'hook'],
                               input=json.dumps(self.payload('Stop')), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout), {})
        # tearDown needs a live connection.
        (self.store.data / 'config.json').unlink()
        self.store = c.Store(self.store.data)

    def test_audit_records_cleanup(self):
        path, mid = self.move()
        actions = [r[0] for r in self.store.db.execute('SELECT action FROM audit')]
        self.assertIn('tracked', actions)
        self.assertIn('plan', actions)
        self.assertIn('quarantine', actions)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name).resolve()
        self.codex_home = self.home / '.codex'
        self.root = self.codex_home / 'plugins/cache/example-marketplace/codex-disk-cleanup/0.1.1'
        manifest = self.root / '.codex-plugin/plugin.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'name': 'codex-disk-cleanup', 'version': '0.1.1'}))
        self.script = self.root / 'scripts/cleanup.py'

    def tearDown(self):
        self.tmp.cleanup()

    def resolve(self, env=None):
        return c.resolve_data(script=self.script, home=self.home, env=env or {})

    def test_native_installation_resolves_host_allocation_without_creating_it(self):
        data, source = self.resolve()
        self.assertEqual(source, 'codex-installation')
        self.assertEqual(data, self.codex_home / 'plugins/data/codex-disk-cleanup-example-marketplace')
        with contextlib.closing(c.Store(data, read_only=True)) as store:
            status = store.status()
            self.assertFalse(status['initialized'])
            self.assertFalse(status['hooks_seen'])
            self.assertEqual(status['auto'], 'preview')
        self.assertFalse(data.exists())

    def test_explicit_and_host_environment_precedence(self):
        env = {'PLUGIN_DATA': str(self.home / 'host'), 'CLAUDE_PLUGIN_DATA': str(self.home / 'compat')}
        self.assertEqual(c.resolve_data(self.home / 'explicit', env=env), (self.home / 'explicit', 'explicit'))
        self.assertEqual(self.resolve(env), (self.home / 'host', 'PLUGIN_DATA'))
        self.assertEqual(self.resolve({'CLAUDE_PLUGIN_DATA': str(self.home / 'compat')}),
                         (self.home / 'compat', 'CLAUDE_PLUGIN_DATA'))

    def test_custom_codex_home(self):
        self.assertEqual(self.resolve({'CODEX_HOME': str(self.codex_home)})[1], 'codex-installation')
        self.assertEqual(self.resolve({'CODEX_HOME': str(self.home / 'other')})[1], 'standalone')

    def test_mismatched_manifest_refused(self):
        (self.root / '.codex-plugin/plugin.json').write_text(json.dumps({'name': 'other', 'version': '0.1.1'}))
        with self.assertRaises(c.Refused):
            self.resolve()

    def test_portable_manifest_in_native_cache_refused(self):
        (self.root / 'plugin.json').write_text('{}')
        with self.assertRaises(c.Refused):
            self.resolve()

    def test_status_command_does_not_initialize_standalone_state(self):
        data = self.home / 'uninitialized'
        proc = subprocess.run([sys.executable, str(SCRIPT), '--data', str(data), 'status'],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        status = json.loads(proc.stdout)
        self.assertFalse(status['initialized'])
        self.assertEqual(status['data_source'], 'explicit')
        self.assertFalse(data.exists())

    def test_status_reads_existing_state_without_mutation(self):
        data = self.home / 'state'
        with contextlib.closing(c.Store(data)) as store:
            store.hook({'hook_event_name': 'SessionStart', 'session_id': 'fixture'})
        before = (data / 'state.sqlite3').read_bytes()
        with contextlib.closing(c.Store(data, read_only=True)) as store:
            self.assertTrue(store.status()['initialized'])
            self.assertTrue(store.status()['hooks_seen'])
            with self.assertRaises(sqlite3.OperationalError):
                store.db.execute("DELETE FROM sessions")
        self.assertEqual((data / 'state.sqlite3').read_bytes(), before)

    def test_read_only_status_rejects_unknown_schema(self):
        data = self.home / 'state'
        with contextlib.closing(c.Store(data)) as store:
            store.db.execute("UPDATE metadata SET value='999' WHERE key='schema'")
        with self.assertRaises(c.Refused):
            c.Store(data, read_only=True)
        # In particular, constructor failure must release the Windows file handle.
        (data / 'state.sqlite3').unlink()

    def test_package_excludes_portable_example(self):
        plugin = SCRIPT.parent.parent
        self.assertFalse((plugin / 'plugin.json').exists())
        self.assertTrue((plugin / '.codex-plugin/plugin.json').is_file())
        package_script = SCRIPT.parents[3] / 'tools/package.py'
        proc = subprocess.run([sys.executable, str(package_script), '--check'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == '__main__':
    unittest.main()
