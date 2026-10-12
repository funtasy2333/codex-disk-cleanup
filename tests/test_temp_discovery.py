import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_cleanup import c, SCRIPT


class TempDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.system = self.base / 'system-temp'
        self.system.mkdir()
        self.project = self.base / 'project'
        self.project.mkdir()
        self.patch = patch.object(c.Store, 'temporary_bases', return_value=[self.system])
        self.patch.start()
        self.store = c.Store(self.base / 'plugin-data')
        self.root = self.system / 'formal-review'

    def tearDown(self):
        self.store.close()
        self.patch.stop()
        self.tmp.cleanup()

    def payload(self, event, command=None, call='one', session='s1', turn='t1', **extra):
        return {'hook_event_name': event, 'session_id': session, 'tool_use_id': call,
                'turn_id': turn, 'cwd': str(self.project), 'tool_name': 'Bash',
                'tool_input': {'command': command or f'mkdir -p "{self.root}"'}, **extra}

    def discover(self, files=()):
        self.store.hook(self.payload('PreToolUse'))
        self.root.mkdir()
        for name in files:
            (self.root / name).write_bytes(b'first call content')
        self.store.hook(self.payload('PostToolUse'))

    def create(self, name='render.png', session='s1'):
        payload = self.payload('PreToolUse', 'python helper.py', call='create', session=session)
        self.store.hook(payload)
        path = self.root / name
        path.write_bytes(b'later generated temporary file')
        payload['hook_event_name'] = 'PostToolUse'
        self.store.hook(payload)
        return path

    def eligible(self):
        self.store.db.execute("UPDATE tracked SET created=created-?", (8 * 86400,))
        return self.store.plan(session='s1', include_busy=True)

    def test_new_literal_directory_discovered_without_guidance_or_config_mutation(self):
        before = dict(self.store.config)
        self.discover()
        roots = self.store.status()['discovered_temp']
        self.assertEqual([r['path'] for r in roots], [str(self.root)])
        self.assertEqual(roots[0]['session'], 's1')
        self.assertEqual(roots[0]['days'], 7)
        self.assertEqual(self.store.config, before)

    def test_dynamic_new_file_tracked_after_discovery(self):
        self.discover()
        path = self.create()
        self.assertEqual([r['path'] for r in self.store.status()['tracked']], [str(path)])

    def test_initial_contents_are_review_only_and_never_adopted(self):
        self.discover(['test_old.txt'])
        self.assertEqual(self.store.status()['tracked'], [])
        reviews = self.store.status()['review_candidates']
        self.assertEqual([r['path'] for r in reviews], [str(self.root / 'test_old.txt')])
        self.create()
        self.assertNotIn(str(self.root / 'test_old.txt'), [r['path'] for r in self.store.status()['tracked']])

    def test_existing_directory_cannot_be_discovered(self):
        self.root.mkdir()
        self.store.hook(self.payload('PreToolUse'))
        (self.root / 'test_new.txt').write_text('new')
        self.store.hook(self.payload('PostToolUse'))
        self.assertEqual(self.store.status()['discovered_temp'], [])
        self.assertEqual(self.store.status()['tracked'], [])

    def test_new_file_directly_in_system_base_does_not_enroll_base(self):
        path = self.system / 'single.png'
        payload = self.payload('PreToolUse', f'python helper.py "{path}"')
        self.store.hook(payload)
        path.write_text('new')
        payload['hook_event_name'] = 'PostToolUse'
        self.store.hook(payload)
        self.assertEqual(self.store.status()['discovered_temp'], [])
        self.assertEqual(self.store.status()['tracked'], [])

    def test_outside_project_literal_creation_is_review_not_owned(self):
        path = self.project / 'final-report.md'
        payload = self.payload('PreToolUse')
        payload['tool_input'] = {'path': str(path)}
        self.store.hook(payload)
        path.write_text('deliverable')
        payload['hook_event_name'] = 'PostToolUse'
        self.store.hook(payload)
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertEqual([r['path'] for r in self.store.status()['review_candidates']], [str(path)])
        self.assertEqual(self.eligible()['items'], [])

    def test_review_observation_does_not_require_content_read_access(self):
        path = self.project / 'report.md'
        payload = self.payload('PreToolUse')
        payload['tool_input'] = {'path': str(path)}
        self.store.hook(payload)
        path.write_text('private deliverable content')
        payload['hook_event_name'] = 'PostToolUse'
        with patch.object(c, 'fingerprint', side_effect=PermissionError('fixture content unreadable')):
            self.store.hook(payload)
        self.assertEqual([r['path'] for r in self.store.status()['review_candidates']], [str(path)])
        self.assertEqual(self.store.status()['tracked'], [])

    def test_modified_preexisting_project_file_is_not_new_observation(self):
        path = self.project / 'existing.md'
        path.write_text('old')
        payload = self.payload('PreToolUse')
        payload['tool_input'] = {'path': str(path)}
        self.store.hook(payload)
        path.write_text('edited')
        payload['hook_event_name'] = 'PostToolUse'
        self.store.hook(payload)
        self.assertEqual(self.store.status()['review_candidates'], [])

    def test_other_session_cannot_adopt_discovered_root_files(self):
        self.discover()
        self.create(session='s2')
        self.assertEqual(self.store.status()['tracked'], [])

    def test_protected_database_rename_in_discovered_root_not_adopted(self):
        self.discover(['important.sqlite3'])
        self.store.hook(self.payload('PreToolUse', 'python helper.py', call='rename'))
        (self.root / 'important.sqlite3').rename(self.root / 'test_new.txt')
        self.store.hook(self.payload('PostToolUse', 'python helper.py', call='rename'))
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertEqual((self.root / 'test_new.txt').read_bytes(), b'first call content')

    def test_discovered_retention_overrides_zero_day_test_filename(self):
        self.discover()
        path = self.create('test_render.png')
        self.assertEqual(self.store.plan(session='s1', include_busy=True)['items'], [])
        self.assertEqual([r['path'] for r in self.eligible()['items']], [str(path)])

    def test_quarantine_restore_and_explicit_purge_use_discovered_root(self):
        self.discover()
        path = self.create()
        result = self.store.apply(self.eligible()['plan_id'])
        self.assertEqual(len(result['quarantined']), 1)
        mid = result['quarantined'][0]
        self.assertTrue((self.root / '.codex-disk-cleanup-quarantine' / mid).is_file())
        self.store.restore(mid)
        self.assertTrue(path.exists())
        other = self.create('other.png')
        mid = self.store.apply(self.eligible()['plan_id'])['quarantined'][0]
        self.store.purge(mid)
        self.assertFalse(other.exists())
        self.assertTrue(path.exists())

    def test_pending_guard_still_blocks_discovered_root(self):
        self.discover()
        path = self.create()
        plan = self.eligible()
        self.store.hook(self.payload('PreToolUse', 'python helper.py', call='busy'))
        result = self.store.apply(plan['plan_id'])
        self.assertEqual(result['quarantined'], [])
        self.assertTrue(path.exists())

    def test_other_session_pending_read_blocks_discovered_root_move(self):
        self.discover()
        path = self.create()
        plan = self.eligible()
        self.store.hook(self.payload('PreToolUse', f'cat "{path}"', call='reader', session='s2'))
        self.assertEqual(self.store.apply(plan['plan_id'])['quarantined'], [])
        self.assertTrue(path.exists())

    def test_other_session_pending_cwd_access_is_reported_blocked(self):
        self.discover()
        path = self.create()
        self.eligible()
        payload = self.payload('PreToolUse', 'python helper.py', call='reader', session='s2')
        payload['cwd'] = str(self.root)
        self.store.hook(payload)
        plan = self.store.plan(session='s1', include_busy=True)
        self.assertEqual([i['path'] for i in plan['blocked']], [str(path)])
        payload['hook_event_name'] = 'PostToolUse'
        self.store.hook(payload)
        self.assertEqual(len(self.store.apply(self.store.plan(session='s1')['plan_id'])['quarantined']), 1)

    def test_foreign_writer_finishing_first_cannot_be_misattributed(self):
        self.discover()
        owner = self.payload('PreToolUse', 'python helper.py', call='owner')
        self.store.hook(owner)
        foreign_path = self.root / 'foreign.txt'
        foreign = self.payload('PreToolUse', f'python helper.py "{foreign_path}"',
                               call='foreign', session='s2')
        self.store.hook(foreign)
        foreign_path.write_text('another session output')
        foreign['hook_event_name'] = 'PostToolUse'
        self.store.hook(foreign)
        owner['hook_event_name'] = 'PostToolUse'
        self.store.hook(owner)
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertTrue(foreign_path.exists())

    def test_foreign_pending_access_before_owner_pre_suspends_adoption(self):
        self.discover()
        self.store.hook(self.payload('PreToolUse', f'ls "{self.root}"', call='foreign', session='s2'))
        self.create()
        self.assertEqual(self.store.status()['tracked'], [])

    def test_foreign_overlap_invalidates_new_directory_discovery(self):
        first = self.payload('PreToolUse', call='first')
        self.store.hook(first)
        self.store.hook(self.payload('PreToolUse', call='foreign', session='s2'))
        self.root.mkdir()
        first['hook_event_name'] = 'PostToolUse'
        self.store.hook(first)
        self.assertEqual(self.store.status()['discovered_temp'], [])

    def test_root_replacement_invalidates_plan_and_reports_error(self):
        self.discover()
        path = self.create()
        plan = self.eligible()
        self.root.rename(self.system / 'original-root')
        self.root.mkdir()
        path.write_bytes(b'replacement')
        self.assertEqual(self.store.apply(plan['plan_id'])['quarantined'], [])
        with contextlib.closing(c.Store(self.store.data, read_only=True)) as again:
            self.assertEqual(again.status()['discovered_temp'], [])
            self.assertTrue(again.status()['discovered_temp_errors'])
        self.assertEqual(path.read_bytes(), b'replacement')

    def test_forget_revokes_plans_without_moving_files(self):
        self.discover()
        path = self.create()
        plan = self.eligible()
        self.store.forget_temp(self.root)
        self.assertEqual(self.store.apply(plan['plan_id'])['quarantined'], [])
        self.assertTrue(path.exists())
        self.assertEqual(self.store.status()['discovered_temp'], [])

    def test_disable_revokes_moves_and_prevents_discovery(self):
        self.discover()
        path = self.create()
        plan = self.eligible()
        self.store.config['discover_temp'] = False
        self.store.save_config()
        self.assertEqual(self.store.apply(plan['plan_id'])['quarantined'], [])
        self.assertTrue(path.exists())
        self.assertEqual([r for r, _ in self.store.managed_roots('s1')], [self.store.workspace('s1')])

    def test_parent_replacement_during_discovery_refused(self):
        parent = self.system / 'parent'
        parent.mkdir()
        self.root = parent / 'new-root'
        self.store.hook(self.payload('PreToolUse'))
        parent.rename(self.system / 'old-parent')
        parent.mkdir()
        self.root.mkdir()
        self.store.hook(self.payload('PostToolUse'))
        self.assertEqual(self.store.status()['discovered_temp'], [])

    def test_cross_turn_discovery_is_invalidated(self):
        self.store.hook(self.payload('PreToolUse', call='first'))
        self.store.hook(self.payload('PreToolUse', call='second', turn='other'))
        self.root.mkdir()
        self.store.hook(self.payload('PostToolUse', call='first'))
        self.assertEqual(self.store.status()['discovered_temp'], [])

    def test_post_without_matching_pre_does_not_discover(self):
        self.root.mkdir()
        self.store.hook(self.payload('PostToolUse'))
        self.assertEqual(self.store.status()['discovered_temp'], [])

    def test_post_with_wrong_turn_cannot_discover(self):
        self.store.hook(self.payload('PreToolUse'))
        self.root.mkdir()
        self.store.hook(self.payload('PostToolUse', turn='wrong-turn'))
        self.assertEqual(self.store.status()['discovered_temp'], [])

    def test_missing_turn_does_not_authorize_discovery(self):
        first = self.payload('PreToolUse')
        first.pop('turn_id')
        self.store.hook(first)
        self.root.mkdir()
        first['hook_event_name'] = 'PostToolUse'
        self.store.hook(first)
        self.assertEqual(self.store.status()['discovered_temp'], [])

    def test_forget_cannot_orphan_unrestored_quarantine(self):
        self.discover()
        self.create()
        mid = self.store.apply(self.eligible()['plan_id'])['quarantined'][0]
        with self.assertRaises(c.Refused):
            self.store.forget_temp(self.root)
        self.store.restore(mid)
        self.store.forget_temp(self.root)
        self.assertEqual(self.store.status()['discovered_temp'], [])

    def test_post_with_wrong_turn_cannot_adopt_dynamic_file(self):
        self.discover()
        self.store.hook(self.payload('PreToolUse', 'python helper.py', call='wrong'))
        path = self.root / 'new.png'
        path.write_bytes(b'new')
        self.store.hook(self.payload('PostToolUse', 'python helper.py', call='wrong', turn='wrong-turn'))
        self.assertEqual(self.store.status()['tracked'], [])

    def test_root_count_limit_is_sixteen_per_session(self):
        for n in range(17):
            self.root = self.system / f'task-{n}'
            self.discover()
        self.assertEqual(len(self.store.status()['discovered_temp']), 16)
        self.assertTrue(self.root.exists())

    def test_over_limit_proposals_do_not_partially_discover(self):
        roots = [self.system / f'task-{n}' for n in range(17)]
        command = 'mkdir ' + ' '.join(f'"{p}"' for p in roots)
        self.store.hook(self.payload('PreToolUse', command))
        for path in roots:
            path.mkdir()
        self.store.hook(self.payload('PostToolUse', command))
        self.assertEqual(self.store.status()['discovered_temp'], [])

    def test_path_prefix_sibling_is_not_system_temp(self):
        sibling = self.base / 'system-temp-other'
        sibling.mkdir()
        self.root = sibling / 'new'
        self.discover()
        self.assertEqual(self.store.status()['discovered_temp'], [])

    def test_codex_home_overlap_never_discovered(self):
        codex = self.system / 'custom-codex'
        codex.mkdir()
        self.root = codex / 'new'
        with patch.dict(os.environ, CODEX_HOME=str(codex)):
            self.discover()
            self.assertEqual(self.store.status()['discovered_temp'], [])

    def test_links_hardlinks_and_database_outputs_not_adopted(self):
        self.discover()
        old = self.project / 'original.txt'
        old.write_text('retained')
        self.store.hook(self.payload('PreToolUse', 'python helper.py', call='links'))
        os.link(old, self.root / 'test_hard.txt')
        (self.root / 'new.sqlite3').write_text('db')
        try:
            (self.root / 'test_link.txt').symlink_to(old)
        except OSError:
            pass
        self.store.hook(self.payload('PostToolUse', 'python helper.py', call='links'))
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertEqual(old.read_text(), 'retained')

    def test_overflow_preserves_cross_root_existing_file(self):
        self.discover(['old.txt', 'one', 'two'])
        with patch.object(c, 'MAX_ITEMS', 2):
            self.store.hook(self.payload('PreToolUse', 'python helper.py', call='overflow'))
            moved = self.store.workspace('s1') / 'test_moved.txt'
            (self.root / 'old.txt').rename(moved)
            self.store.hook(self.payload('PostToolUse', 'python helper.py', call='overflow'))
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertTrue(moved.exists())

    def test_discovery_off_cli_preserves_quarantine_mode(self):
        self.store.config['auto'] = 'quarantine'
        self.store.save_config()
        proc = subprocess.run([sys.executable, str(SCRIPT), '--data', str(self.store.data),
                               'init', '--discover-temp', 'off'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertFalse(result['discover_temp'])
        self.assertEqual(result['auto'], 'quarantine')

    def test_forget_cli_requires_yes_and_keeps_files(self):
        self.discover(['retained.txt'])
        command = [sys.executable, str(SCRIPT), '--data', str(self.store.data), 'forget-temp',
                   '--root', str(self.root)]
        proc = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        proc = subprocess.run([*command, '--yes'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.root / 'retained.txt').exists())
        self.assertEqual(self.store.status()['discovered_temp'], [])

    def test_temp_alias_is_normalized_but_custom_links_are_not(self):
        if os.name == 'nt' or not Path('/tmp').is_symlink():
            self.skipTest('OS /tmp alias unavailable')
        with tempfile.TemporaryDirectory(dir='/tmp') as t:
            canonical = Path(t).resolve()
            self.root = canonical / 'new-root'
            literal = Path('/tmp') / canonical.name / 'new-root'
            with patch.object(c.Store, 'temporary_bases', return_value=[Path('/tmp').resolve()]):
                command = f'mkdir "{literal}"'
                self.store.hook(self.payload('PreToolUse', command))
                self.root.mkdir()
                self.store.hook(self.payload('PostToolUse', command))
                self.assertEqual([r['path'] for r in self.store.status()['discovered_temp']], [str(self.root)])

    def test_protected_names_and_git_roots_refused(self):
        for name in ['outputs', '.codex', '.ssh']:
            self.root = self.system / name
            self.discover()
        self.root = self.system / 'git-root'
        self.store.hook(self.payload('PreToolUse'))
        self.root.mkdir()
        (self.root / '.git').mkdir()
        self.store.hook(self.payload('PostToolUse'))
        self.assertEqual(self.store.status()['discovered_temp'], [])

    def test_symlink_parent_not_followed(self):
        link = self.system / 'link'
        try:
            link.symlink_to(self.project, target_is_directory=True)
        except OSError:
            self.skipTest('symlink creation unavailable')
        self.root = link / 'new-root'
        self.discover()
        self.assertEqual(self.store.status()['discovered_temp'], [])

    def test_failed_first_call_binds_directory_but_not_file_ownership(self):
        self.store.hook(self.payload('PreToolUse'))
        self.root.mkdir()
        (self.root / 'initial.txt').write_text('partial output')
        self.store.hook(self.payload('PostToolUse', tool_response={'exit_code': 2}))
        self.assertEqual(len(self.store.status()['discovered_temp']), 1)
        self.assertEqual(self.store.status()['tracked'], [])
        self.create()
        self.assertEqual(len(self.store.status()['tracked']), 1)

    def test_failed_later_call_does_not_adopt_new_files(self):
        self.discover()
        self.store.hook(self.payload('PreToolUse', 'python helper.py', call='failed'))
        (self.root / 'partial.txt').write_text('partial')
        self.store.hook(self.payload('PostToolUse', 'python helper.py', call='failed',
                                     tool_response={'exit_code': 1}))
        self.assertEqual(self.store.status()['tracked'], [])

    def test_cli_actual_dynamic_python_output_tracked_in_discovered_root(self):
        env = dict(os.environ, TMPDIR=str(self.system), TEMP=str(self.system), TMP=str(self.system))
        hook = [sys.executable, str(SCRIPT), '--data', str(self.store.data), 'hook']
        for event in ['PreToolUse', 'PostToolUse']:
            if event == 'PostToolUse':
                self.root.mkdir()
            result = subprocess.run(hook, env=env, input=json.dumps(self.payload(event)),
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        payload = self.payload('PreToolUse', 'python helper.py', call='generator')
        subprocess.run(hook, env=env, input=json.dumps(payload), capture_output=True, text=True, check=True)
        subprocess.run([sys.executable, '-c', "import os;from pathlib import Path;"
                        "r=Path(os.environ['TASK_GENERATED_ROOT']);"
                        "[(r/f'crop-{n}.png').write_bytes(b'new') for n in range(3)]"],
                       env={**env, 'TASK_GENERATED_ROOT': str(self.root)}, check=True)
        payload['hook_event_name'] = 'PostToolUse'
        subprocess.run(hook, env=env, input=json.dumps(payload), capture_output=True, text=True, check=True)
        with contextlib.closing(c.Store(self.store.data, read_only=True)) as status_store:
            self.assertEqual(len(status_store.status()['tracked']), 3)

    def test_old_schema_read_only_status_without_optional_tables(self):
        self.store.db.execute('DROP TABLE discovered_temp')
        self.store.db.execute('DROP TABLE review_candidates')
        with contextlib.closing(c.Store(self.store.data, read_only=True)) as old:
            self.assertEqual(old.status()['discovered_temp'], [])
            self.assertEqual(old.status()['review_candidates'], [])
