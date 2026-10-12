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


class ProjectScratchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.store = c.Store(self.base / 'state')
        self.project = self.base / 'project'
        self.root = self.project / 'disposable'
        self.root.mkdir(parents=True)
        self.builtin = self.store.workspace('s1')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def enroll(self, days=0):
        return self.store.enroll(self.project, self.root, 's1', days)['enrolled']

    def payload(self, event, session='s1', call='dynamic', cmd='python script.py', turn='t1'):
        return {'hook_event_name': event, 'session_id': session, 'tool_use_id': call,
                'turn_id': turn, 'cwd': str(self.project), 'tool_name': 'Bash',
                'tool_input': {'command': cmd}}

    def create(self, root=None, name='preview.png', session='s1'):
        root = root or self.root
        path = root / name
        self.store.hook(self.payload('PreToolUse', session=session))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'temporary image fixture')
        self.store.hook(self.payload('PostToolUse', session=session))
        return path

    def plan(self):
        return self.store.plan(session='s1', include_busy=True)

    def test_dynamic_builtin_files_tracked_without_literal_paths(self):
        first = self.create(self.builtin, 'subdir/a.png')
        second = self.create(self.builtin, 'subdir/b.png')
        self.assertEqual({r['path'] for r in self.store.status()['tracked']}, {str(first), str(second)})

    def test_enrolled_dynamic_project_file_previewed_and_retained(self):
        self.enroll()
        path = self.create()
        plan = self.plan()
        self.assertEqual([i['path'] for i in plan['items']], [str(path)])
        self.assertEqual(plan['bytes'], path.stat().st_size)
        self.assertTrue(plan['plan_id'])
        self.assertEqual(plan['items'][0]['project_policy']['session'], 's1')
        self.assertTrue(path.exists())

    def test_multiple_dynamic_files_in_one_call(self):
        self.enroll()
        self.store.hook(self.payload('PreToolUse'))
        for name in ['a.png', 'b.txt', 'c.json']:
            (self.root / name).write_text(name)
        self.store.hook(self.payload('PostToolUse'))
        self.assertEqual(len(self.plan()['items']), 3)

    def test_cli_hooks_capture_actual_python_loop_with_variable_paths(self):
        self.enroll()
        source = self.project / 'generator.py'
        source.write_text("from pathlib import Path\nimport os\n"
                          "root=Path(os.environ['TASK_OUTPUT'])\n"
                          "for i in range(3):\n"
                          " (root/f'crop-{i}.png').write_bytes(b'temporary')\n")
        payload = self.payload('PreToolUse', cmd=f'python {source}')
        hook = [sys.executable, str(SCRIPT), '--data', str(self.store.data), 'hook']
        proc = subprocess.run(hook, input=json.dumps(payload), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        subprocess.run([sys.executable, str(source)], check=True,
                       env={**os.environ, 'TASK_OUTPUT': str(self.root)})
        payload['hook_event_name'] = 'PostToolUse'
        proc = subprocess.run(hook, input=json.dumps(payload), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual({r['path'] for r in self.store.status()['tracked']},
                         {str(self.root / f'crop-{i}.png') for i in range(3)})
        self.assertTrue(source.exists())

    def test_snapshot_budget_is_shared_across_roots(self):
        self.enroll()
        (self.builtin / 'existing.txt').write_text('old')
        (self.root / 'existing.txt').write_text('old')
        with patch.object(c, 'MAX_ITEMS', 2):
            self.create(name='third.png')
        self.assertEqual(self.store.status()['tracked'], [])

    def test_overflow_does_not_restart_budget_for_later_roots(self):
        self.enroll()
        second = self.project / 'second-disposable'
        second.mkdir()
        self.store.enroll(self.project, second, 's1', 0)
        for name in ['one', 'two', 'three']:
            (self.root / name).write_text(name)
        with patch.object(c, 'MAX_ITEMS', 2), patch.object(self.store, 'snapshot', wraps=self.store.snapshot) as scan:
            self.store.hook(self.payload('PreToolUse'))
            self.assertEqual(scan.call_count, 2)  # builtin root, then overflowing first project root
        self.assertEqual(self.store.status()['tracked'], [])

    def test_literal_renamed_existing_file_protected_when_snapshots_overflow(self):
        self.enroll()
        old = self.root / 'old.png'
        old.write_bytes(b'original')
        for name in ['one', 'two', 'three']:
            (self.root / name).write_text(name)
        new = self.root / 'test_new.png'
        payload = self.payload('PreToolUse', cmd=f'mv {old} {new}')
        with patch.object(c, 'MAX_ITEMS', 2):
            self.store.hook(payload)
            old.rename(new)
            payload['hook_event_name'] = 'PostToolUse'
            self.store.hook(payload)
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertEqual(new.read_bytes(), b'original')

    def test_enrollment_and_snapshots_do_not_adopt_existing_files(self):
        old = self.root / 'existing.png'
        old.write_bytes(b'original')
        self.enroll()
        path = self.create()
        self.assertEqual([i['path'] for i in self.plan()['items']], [str(path)])
        self.assertEqual(old.read_bytes(), b'original')

    def test_preexisting_file_modified_in_call_is_not_adopted(self):
        old = self.root / 'existing.png'
        old.write_bytes(b'original')
        self.enroll()
        self.store.hook(self.payload('PreToolUse'))
        old.write_bytes(b'edited by tool')
        self.store.hook(self.payload('PostToolUse'))
        self.assertEqual(self.store.status()['tracked'], [])

    def test_renamed_existing_file_is_not_adopted(self):
        old = self.root / 'existing.png'
        old.write_bytes(b'original')
        self.enroll()
        renamed = self.root / 'test_renamed.png'
        before = self.payload('PreToolUse', cmd=f'mv {old} {renamed}')
        self.store.hook(before)
        old.rename(renamed)
        before['hook_event_name'] = 'PostToolUse'
        self.store.hook(before)
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertEqual(renamed.read_bytes(), b'original')

    def test_protected_existing_database_renamed_dynamically_is_not_adopted(self):
        self.enroll()
        old = self.root / 'important.sqlite3'
        old.write_bytes(b'original database')
        self.store.hook(self.payload('PreToolUse'))
        new = self.root / 'test_new.txt'
        old.rename(new)
        self.store.hook(self.payload('PostToolUse'))
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertEqual(self.plan()['items'], [])
        self.assertEqual(new.read_bytes(), b'original database')

    def test_protected_subtree_existing_file_moved_out_is_not_adopted(self):
        self.enroll()
        protected = self.root / 'outputs'
        protected.mkdir()
        old = protected / 'retained.txt'
        old.write_bytes(b'original evidence')
        self.store.hook(self.payload('PreToolUse'))
        new = self.root / 'test_new.txt'
        old.rename(new)
        self.store.hook(self.payload('PostToolUse'))
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertEqual(new.read_bytes(), b'original evidence')

    def test_overflowing_root_existing_file_moved_to_other_root_is_not_adopted(self):
        self.enroll()
        for name in ['old.txt', 'two', 'three']:
            (self.root / name).write_text('original')
        with patch.object(c, 'MAX_ITEMS', 2):
            self.store.hook(self.payload('PreToolUse'))
            new = self.builtin / 'test_new.txt'
            (self.root / 'old.txt').rename(new)
            self.store.hook(self.payload('PostToolUse'))
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertEqual(self.plan()['items'], [])
        self.assertEqual(new.read_text(), 'original')

    def test_overflow_protected_source_literal_rename_is_not_adopted(self):
        self.enroll()
        old = self.root / 'important.sqlite3'
        old.write_bytes(b'original database')
        for name in ['two', 'three']:
            (self.root / name).write_text('old')
        new = self.root / 'test_new.txt'
        payload = self.payload('PreToolUse', cmd=f'mv {old} {new}')
        with patch.object(c, 'MAX_ITEMS', 2):
            self.store.hook(payload)
            old.rename(new)
            payload['hook_event_name'] = 'PostToolUse'
            self.store.hook(payload)
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertEqual(new.read_bytes(), b'original database')

    def test_overflow_literal_destination_alone_cannot_prove_creation(self):
        self.enroll()
        old = self.root / 'old.txt'
        old.write_bytes(b'original')
        for name in ['two', 'three']:
            (self.root / name).write_text('old')
        new = self.builtin / 'test_new.txt'
        payload = self.payload('PreToolUse', cmd=f'python helper.py --destination {new}')
        with patch.object(c, 'MAX_ITEMS', 2):
            self.store.hook(payload)
            old.rename(new)
            payload['hook_event_name'] = 'PostToolUse'
            self.store.hook(payload)
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertEqual(new.read_bytes(), b'original')

    def test_cross_turn_invalidation_cannot_restore_unsafe_literal_adoption(self):
        self.enroll()
        old = self.root / 'important.sqlite3'
        old.write_bytes(b'original database')
        new = self.root / 'test_new.txt'
        first = self.payload('PreToolUse', call='first', cmd=f'mv {old} {new}')
        self.store.hook(first)
        self.store.hook(self.payload('PreToolUse', call='second', turn='t2'))
        old.rename(new)
        first['hook_event_name'] = 'PostToolUse'
        self.store.hook(first)
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertEqual(new.read_bytes(), b'original database')

    def test_existing_file_moved_between_managed_roots_is_not_adopted(self):
        self.enroll()
        old = self.builtin / 'existing.png'
        old.write_bytes(b'original')
        self.store.hook(self.payload('PreToolUse'))
        moved = self.root / 'moved.png'
        old.rename(moved)
        self.store.hook(self.payload('PostToolUse'))
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertEqual(moved.read_bytes(), b'original')

    def test_unregistered_project_directory_not_tracked(self):
        path = self.create()
        self.assertTrue(path.exists())
        self.assertEqual(self.store.status()['tracked'], [])

    def test_file_outside_enrolled_directory_not_tracked(self):
        self.enroll()
        path = self.create(self.project, 'final.png')
        self.assertTrue(path.exists())
        self.assertEqual(self.store.status()['tracked'], [])

    def test_root_is_bound_to_one_session(self):
        self.enroll()
        path = self.create(session='other')
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertTrue(path.exists())

    def test_project_retention_overrides_test_filename(self):
        self.enroll(days=7)
        path = self.create(name='test_a.py')
        self.assertEqual(self.plan()['items'], [])
        self.store.db.execute('UPDATE tracked SET created=0')
        self.assertEqual(self.plan()['items'][0]['path'], str(path))

    def test_pending_guard_blocks_project_move(self):
        self.enroll()
        path = self.create()
        self.store.hook(self.payload('PreToolUse', call='running'))
        plan = self.plan()
        self.assertEqual(len(plan['blocked']), 1)
        self.assertEqual(self.store.apply(plan['plan_id'])['quarantined'], [])
        self.assertTrue(path.exists())

    def test_modified_project_file_is_preserved(self):
        self.enroll()
        path = self.create()
        plan = self.plan()
        path.write_bytes(b'important revision')
        self.assertEqual(self.store.apply(plan['plan_id'])['quarantined'], [])
        self.assertTrue(path.exists())

    def test_withdraw_enrollment_invalidates_plan_without_removing_files(self):
        self.enroll()
        path = self.create()
        plan = self.plan()
        self.store.unenroll(self.root)
        self.assertEqual(self.store.apply(plan['plan_id'])['quarantined'], [])
        self.assertTrue(path.exists())
        self.assertEqual(len(self.store.status()['tracked']), 1)

    def test_withdraw_during_call_does_not_track_project_files(self):
        self.enroll()
        self.store.hook(self.payload('PreToolUse'))
        self.store.unenroll(self.root)
        (self.root / 'new.png').write_bytes(b'new')
        self.store.hook(self.payload('PostToolUse'))
        self.assertEqual(self.store.status()['tracked'], [])

    def test_project_quarantine_restore_and_explicit_purge(self):
        self.enroll()
        path = self.create()
        mid = self.store.apply(self.plan()['plan_id'])['quarantined'][0]
        self.assertFalse(path.exists())
        self.store.restore(mid)
        self.assertTrue(path.exists())
        path.unlink()  # Only this isolated fixture; make a new observed creation.
        path = self.create()
        mid = self.store.apply(self.plan()['plan_id'])['quarantined'][0]
        self.store.purge(mid)
        self.assertEqual(self.store.status()['quarantine'], [])

    def test_root_replacement_prevents_tracking_and_is_reported(self):
        self.enroll()
        self.store.hook(self.payload('PreToolUse'))
        self.root.rename(self.project / 'old-root')
        self.root.mkdir()
        (self.root / 'new.png').write_bytes(b'new')
        self.store.hook(self.payload('PostToolUse'))
        self.assertEqual(self.store.status()['tracked'], [])
        with contextlib.closing(c.Store(self.store.data, read_only=True)) as reopened:
            self.assertEqual(reopened.project_roots, [])
            self.assertIn('identity', reopened.project_errors[0]['reason'])

    def test_missing_root_can_be_unenrolled(self):
        self.enroll()
        self.root.rmdir()
        with contextlib.closing(c.Store(self.store.data)) as reopened:
            self.assertEqual(len(reopened.project_errors), 1)
            reopened.unenroll(self.root)
            self.assertEqual(reopened.config['project_scratch'], [])

    def test_overlapping_and_cross_session_enrollments_refused(self):
        self.enroll()
        child = self.root / 'nested'
        child.mkdir()
        for root in [self.root, child]:
            with self.subTest(root=root), self.assertRaises(c.Refused):
                self.store.enroll(self.project, root, 'other', 7)

    def test_project_root_protected_names_and_git_trees_refused(self):
        with self.assertRaises(c.Refused):
            self.store.enroll(self.project, self.project, 's1', 7)
        outputs = self.project / 'outputs'
        outputs.mkdir()
        with self.assertRaises(c.Refused):
            self.store.enroll(self.project, outputs, 's1', 7)
        (self.project / '.git').mkdir()
        with self.assertRaises(c.Refused):
            self.enroll()

    def test_home_and_codex_data_enrollment_refused(self):
        with patch.object(Path, 'home', return_value=self.project):
            with self.assertRaises(c.Refused):
                self.enroll()
        with patch.dict(os.environ, {'CODEX_HOME': str(self.project)}):
            with self.assertRaises(c.Refused):
                self.enroll()

    def test_sensitive_project_ancestor_refused(self):
        for name in ['.ssh', 'memories', 'plugins']:
            project = self.base / name
            root = project / 'disposable'
            root.mkdir(parents=True)
            with self.subTest(name=name), self.assertRaises(c.Refused):
                self.store.enroll(project, root, 's1', 7)

    def test_snapshot_protects_database_outputs_links_and_hardlinks(self):
        self.enroll()
        self.store.hook(self.payload('PreToolUse'))
        (self.root / 'state.sqlite3').write_bytes(b'database')
        (self.root / 'outputs').mkdir()
        (self.root / 'outputs/final.png').write_bytes(b'final')
        victim = self.project / 'original.png'
        victim.write_bytes(b'original')
        os.link(victim, self.root / 'hardlink.png')
        try:
            (self.root / 'link.png').symlink_to(victim)
        except OSError:
            pass
        self.store.hook(self.payload('PostToolUse'))
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertEqual(victim.read_bytes(), b'original')

    def test_snapshot_limit_fails_closed_without_adopting_files(self):
        self.enroll()
        for name in ['one', 'two', 'three']:
            (self.root / name).write_text(name)
        with patch.object(c, 'MAX_ITEMS', 2):
            self.create(name='new.png')
        self.assertEqual(self.store.status()['tracked'], [])
        reasons = [json.loads(r[0])['reason'] for r in self.store.db.execute(
            "SELECT detail FROM audit WHERE action='coverage-skipped'")]
        self.assertTrue(any('2000 entries' in reason for reason in reasons))

    def test_old_pending_list_format_is_still_supported(self):
        path = self.builtin / 'test_old.py'
        payload = self.payload('PreToolUse', cmd=f'touch {path}')
        self.store.hook(payload)
        self.store.db.execute('UPDATE pending SET paths=?', (json.dumps([str(path)]),))
        path.write_text('new')
        payload['hook_event_name'] = 'PostToolUse'
        self.store.hook(payload)
        self.assertEqual(self.store.status()['tracked'][0]['path'], str(path))

    def test_overlapping_turns_invalidate_dynamic_snapshots(self):
        self.enroll()
        self.store.hook(self.payload('PreToolUse', call='first', turn='t1'))
        self.store.hook(self.payload('PreToolUse', call='second', turn='t2'))
        path = self.root / 'ambiguous.png'
        path.write_bytes(b'new')
        self.store.hook(self.payload('PostToolUse', call='second', turn='t2'))
        self.store.hook(self.payload('PostToolUse', call='first', turn='t1'))
        self.assertEqual(self.store.status()['tracked'], [])
        self.assertTrue(path.exists())

    def test_auto_project_stop_only_moves_current_turn(self):
        self.enroll()
        old = self.create(name='old.png')
        self.store.db.execute("UPDATE tracked SET turn='old' WHERE path=?", (str(old),))
        current = self.create(name='current.png')
        self.store.config['auto'] = 'quarantine'
        self.store.hook(self.payload('Stop'))
        self.assertTrue(old.exists())
        self.assertFalse(current.exists())

    def test_project_preview_stop_preserves_files(self):
        self.enroll()
        path = self.create()
        result = self.store.hook(self.payload('Stop'))
        self.assertEqual(result['preview']['items'][0]['path'], str(path))
        self.assertTrue(path.exists())

    def test_root_identity_changed_after_quarantine_refuses_purge(self):
        self.enroll()
        self.create()
        mid = self.store.apply(self.plan()['plan_id'])['quarantined'][0]
        self.root.rename(self.project / 'old-root')
        self.root.mkdir()
        with self.assertRaises(c.Refused):
            self.store.purge(mid)
        self.assertTrue((self.project / 'old-root/.codex-disk-cleanup-quarantine' / mid).exists())

    def test_enroll_cli_requires_explicit_confirmation_and_preserves_auto(self):
        command = [sys.executable, str(SCRIPT), '--data', str(self.store.data), 'enroll',
                   '--project', str(self.project), '--root', str(self.root), '--session', 's1']
        proc = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('--yes', proc.stderr)
        proc = subprocess.run([*command, '--yes'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with contextlib.closing(c.Store(self.store.data, read_only=True)) as reopened:
            self.assertEqual(reopened.config['auto'], 'preview')
            self.assertEqual(reopened.project_roots[0]['days'], 7)
            self.assertEqual(reopened.status()['tracked'], [])
