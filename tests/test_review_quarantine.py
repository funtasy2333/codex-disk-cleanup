import contextlib
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

from test_cleanup import c, SCRIPT


class ReviewQuarantineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.project = self.base / 'mixed-project'
        self.project.mkdir()
        self.store = c.Store(self.base / 'data')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def observe(self, name='render.txt', session='s1'):
        path = self.project / name
        path.write_text('disposable rendering check', encoding='utf-8')
        self.store.record_review(path, session, 'outside-managed-literal', 't1')
        return path

    def listed(self, path, session='s1'):
        return next(x for x in self.store.review_list(session)['items'] if x['path'] == str(path))

    def mark(self, path, choice='quarantine', session='s1', purpose='one-use rendering check'):
        row = self.listed(path, session)
        return self.store.review_mark(row['candidate_id'], session, choice, purpose, row['snapshot'])

    def plan(self, path=None):
        path = path or self.observe()
        self.mark(path)
        return path, self.store.review_plan('s1')

    def apply(self, plan):
        return self.store.apply(plan['plan_id'], review_digest=plan['digest'])

    def pending(self, paths=(), session='s2', **extra):
        evidence = {'absent': [], 'snapshots': [], 'turn': 't1',
                    'access_paths': [str(p) for p in paths], 'temp_access': []}
        evidence.update(extra)
        self.store.db.execute('INSERT INTO pending VALUES (?,?,?,?)',
                              (session, 'busy', time.time(), c.compact(evidence)))

    def test_list_shows_unknown_use_size_source_and_moves_nothing(self):
        path = self.observe()
        row = self.listed(path)
        self.assertEqual(row['purpose'], None)
        self.assertEqual(row['decision'], 'unreviewed')
        self.assertEqual(row['reason'], 'outside-managed-literal')
        self.assertEqual(row['bytes'], 26)
        self.assertEqual(row['current_fp']['ino'], path.stat().st_ino)
        self.assertEqual(row['current_parent']['ino'], self.project.stat().st_ino)
        self.assertTrue(path.exists())
        self.assertEqual(self.store.status()['quarantine'], [])

    def test_list_does_not_read_content(self):
        path = self.observe()
        with patch.object(c, 'fingerprint', side_effect=AssertionError('content read')):
            self.assertEqual(self.listed(path)['state'], 'available')

    def test_keep_mark_retains_file_and_produces_no_move_plan(self):
        path = self.observe()
        self.mark(path, 'keep', purpose='retained source')
        self.assertEqual(self.listed(path)['purpose'], 'retained source')
        self.assertEqual(self.store.review_plan('s1')['items'], [])
        self.assertTrue(path.exists())

    def test_unreviewed_file_cannot_enter_plan(self):
        path = self.observe()
        self.assertEqual(self.store.review_plan('s1')['items'], [])
        self.assertTrue(path.exists())

    def test_confirmed_file_quarantines_restores_and_preserves_neighbor(self):
        path = self.observe()
        neighbor = self.project / 'final-report.txt'
        neighbor.write_text('retained final report')
        self.mark(path)
        plan = self.store.review_plan('s1')
        self.assertEqual([x['path'] for x in plan['items']], [str(path)])
        self.assertEqual(plan['bytes'], 26)
        self.assertTrue(path.exists())
        result = self.apply(plan)
        self.assertEqual(result['skipped'], [])
        mid = result['quarantined'][0]
        self.assertFalse(path.exists())
        self.assertEqual(neighbor.read_text(), 'retained final report')
        with contextlib.closing(c.Store(self.store.data)) as again:
            again.restore(mid)
            self.assertEqual(again.review_list('s1')['items'][0]['decision'], 'keep')
        self.assertEqual(path.read_text(), 'disposable rendering check')

    def test_mark_requires_displayed_snapshot(self):
        path = self.observe()
        row = self.listed(path)
        with self.assertRaises(c.Refused):
            self.store.review_mark(row['candidate_id'], 's1', 'quarantine', 'temporary', 'bad')
        self.assertTrue(path.exists())

    def test_mark_requires_nonempty_purpose(self):
        path = self.observe()
        with self.assertRaises(c.Refused):
            self.mark(path, purpose='  ')

    def test_changed_file_cannot_use_stale_display_token(self):
        path = self.observe()
        row = self.listed(path)
        path.write_text('important revision')
        with self.assertRaises(c.Refused):
            self.store.review_mark(row['candidate_id'], 's1', 'quarantine', 'temporary', row['snapshot'])
        self.assertEqual(self.listed(path)['state'], 'changed')

    def test_explicit_new_display_can_review_changed_version(self):
        path = self.observe()
        path.write_text('new version explicitly reviewed')
        self.mark(path)
        self.assertEqual(len(self.apply(self.store.review_plan('s1'))['quarantined']), 1)

    def test_wrong_session_cannot_mark_another_candidate(self):
        path = self.observe()
        row = self.listed(path)
        with self.assertRaises(c.Refused):
            self.store.review_mark(row['candidate_id'], 's2', 'quarantine', 'temporary', row['snapshot'])

    def test_normal_apply_cannot_bypass_confirmation_digest(self):
        path, plan = self.plan()
        with self.assertRaises(c.Refused):
            self.store.apply(plan['plan_id'])
        self.assertTrue(path.exists())
        self.assertEqual(len(self.apply(plan)['quarantined']), 1)

    def test_wrong_digest_does_not_consume_plan(self):
        path, plan = self.plan()
        with self.assertRaises(c.Refused):
            self.store.apply(plan['plan_id'], review_digest='0' * 64)
        self.assertEqual(len(self.apply(plan)['quarantined']), 1)

    def test_explicit_subset_does_not_include_other_marked_file(self):
        a, b = self.observe('a.txt'), self.observe('b.txt')
        self.mark(a)
        self.mark(b)
        plan = self.store.review_plan('s1', [self.listed(a)['candidate_id']])
        self.assertEqual(len(self.apply(plan)['quarantined']), 1)
        self.assertFalse(a.exists())
        self.assertTrue(b.exists())

    def test_unknown_selection_fails_closed(self):
        self.observe()
        with self.assertRaises(c.Refused):
            self.store.review_plan('s1', ['0' * 32])

    def test_keep_selection_cannot_be_confirmed_as_quarantine(self):
        path = self.observe()
        self.mark(path, 'keep')
        with self.assertRaises(c.Refused):
            self.store.review_plan('s1', [self.listed(path)['candidate_id']])

    def test_keep_revokes_existing_plan(self):
        path, plan = self.plan()
        self.mark(path, 'keep')
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_reapproval_revokes_older_decision_plan(self):
        path, plan = self.plan()
        self.mark(path, purpose='new review decision')
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_modified_after_mark_skips_plan(self):
        path = self.observe()
        self.mark(path)
        path.write_text('important update')
        self.assertEqual(self.store.review_plan('s1')['items'], [])

    def test_modified_after_confirmation_does_not_move(self):
        path, plan = self.plan()
        path.write_text('important update')
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_parent_replacement_revokes_plan(self):
        path, plan = self.plan()
        old = self.base / 'previous-parent'
        self.project.rename(old)
        self.project.mkdir()
        (old / path.name).rename(path)
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_pending_owner_blocks_review_move(self):
        path, plan = self.plan()
        self.pending(session='s1')
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_foreign_pending_parent_access_blocks_move(self):
        path, plan = self.plan()
        self.pending([self.project])
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_unrelated_foreign_pending_allows_move(self):
        path, plan = self.plan()
        self.pending([self.base / 'other-project'])
        self.assertEqual(len(self.apply(plan)['quarantined']), 1)

    def test_legacy_pending_with_unknown_full_access_blocks_move(self):
        path, plan = self.plan()
        self.store.db.execute('INSERT INTO pending VALUES (?,?,?,?)', ('s2', 'old', time.time(), '[]'))
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_pending_overflow_blocks_move(self):
        path, plan = self.plan()
        self.pending(incomplete_access=True)
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_expired_and_reused_plans_do_not_move(self):
        path, plan = self.plan()
        self.store.db.execute('UPDATE plans SET created=created-? WHERE id=?', (901, plan['plan_id']))
        with self.assertRaises(c.Refused):
            self.apply(plan)
        self.assertTrue(path.exists())
        new = self.store.review_plan('s1')
        self.apply(new)
        with self.assertRaises(c.Refused):
            self.apply(new)

    def test_restore_cannot_overwrite_replacement(self):
        path, plan = self.plan()
        mid = self.apply(plan)['quarantined'][0]
        path.write_text('replacement file')
        with self.assertRaises(c.Refused):
            self.store.restore(mid)
        self.assertEqual(path.read_text(), 'replacement file')

    def test_queue_eviction_does_not_remove_restore_authority(self):
        path, plan = self.plan()
        mid = self.apply(plan)['quarantined'][0]
        self.store.db.execute('DELETE FROM review_candidates')
        self.store.db.execute('DELETE FROM review_decisions')
        with contextlib.closing(c.Store(self.store.data)) as again:
            again.restore(mid)
            self.assertEqual(again.db.execute("SELECT count(*) FROM review_decisions WHERE path=? AND decision='keep'",
                                              (str(path),)).fetchone()[0], 1)
        self.assertTrue(path.exists())

    def test_candidate_eviction_before_apply_revokes_plan(self):
        path, plan = self.plan()
        self.store.db.execute('DELETE FROM review_candidates')
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_review_purge_is_explicit_and_durable(self):
        path, plan = self.plan()
        mid = self.apply(plan)['quarantined'][0]
        self.store.purge(mid)
        self.assertFalse(path.exists())
        self.assertEqual(self.store.db.execute('SELECT state FROM moves WHERE id=?', (mid,)).fetchone()[0], 'purged')

    def test_protected_path_added_after_review_is_refused(self):
        path, plan = self.plan()
        (self.project / '.git').mkdir()
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_link_and_hardlink_replacements_are_refused(self):
        path, plan = self.plan()
        original = self.project / 'original.txt'
        path.rename(original)
        os.link(original, path)
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_custom_codex_home_cannot_be_manually_approved(self):
        path, plan = self.plan()
        with patch.dict(os.environ, CODEX_HOME=str(self.project)):
            self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_keep_prevents_automatic_tracked_move(self):
        self.store.enroll(self.base, self.project, 's1', 0)
        path = self.project / 'test_owned.txt'
        before = {'hook_event_name': 'PreToolUse', 'session_id': 's1', 'turn_id': 't1',
                  'tool_use_id': 'one', 'cwd': str(self.project), 'tool_input': {'path': str(path)}}
        self.store.hook(before)
        path.write_text('temporary contents')
        before['hook_event_name'] = 'PostToolUse'
        self.store.hook(before)
        self.store.record_review(path, 's1', 'initial-temp-contents', 't1')
        automatic = self.store.plan(session='s1')
        self.mark(path, 'keep')
        self.assertEqual(self.store.apply(automatic['plan_id'])['quarantined'], [])
        self.assertTrue(path.exists())

    def test_readonly_listing_on_old_schema_adds_no_tables(self):
        self.store.db.execute('DROP TABLE review_decisions')
        self.store.db.execute('DROP TABLE review_moves')
        self.store.close()
        with contextlib.closing(c.Store(self.base / 'data', read_only=True)) as old:
            self.assertEqual(old.review_list()['items'], [])
            self.assertFalse(old.has_table('review_decisions'))

    def test_cli_review_list_does_not_initialize_missing_data(self):
        data = self.base / 'missing-data'
        result = subprocess.run([sys.executable, str(SCRIPT), '--data', str(data), 'review-list'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['items'], [])
        self.assertFalse(data.exists())

    def test_cli_complete_flow_requires_exact_digest_and_yes(self):
        path = self.observe()
        def run(*args):
            return subprocess.run([sys.executable, str(SCRIPT), '--data', str(self.store.data), *args], capture_output=True, text=True)
        row = json.loads(run('review-list', '--session', 's1').stdout)['items'][0]
        marked = run('review-mark', '--session', 's1', '--candidate', row['candidate_id'],
                     '--snapshot', row['snapshot'], '--decision', 'quarantine', '--purpose', 'render check')
        self.assertEqual(marked.returncode, 0, marked.stderr)
        plan = json.loads(run('review-plan', '--session', 's1').stdout)
        rejected = run('review-apply', plan['plan_id'], '--digest', plan['digest'])
        self.assertNotEqual(rejected.returncode, 0)
        self.assertTrue(path.exists())
        result = run('review-apply', plan['plan_id'], '--digest', plan['digest'], '--yes')
        self.assertEqual(result.returncode, 0, result.stderr)
        mid = json.loads(result.stdout)['quarantined'][0]
        self.assertEqual(run('restore', mid).returncode, 0)
        self.assertTrue(path.exists())

    def test_change_between_snapshot_validation_and_hash_is_refused(self):
        path = self.observe()
        row = self.listed(path)
        original = self.store.review_file
        calls = 0
        def changing_file(value):
            nonlocal calls
            calls += 1
            if calls == 2:
                path.write_text('new important contents')
            return original(value)
        with patch.object(self.store, 'review_file', side_effect=changing_file):
            with self.assertRaises(c.Refused):
                self.store.review_mark(row['candidate_id'], 's1', 'quarantine', 'temporary', row['snapshot'])
        self.assertTrue(path.exists())

    def test_keep_from_other_session_cannot_be_overridden_by_plan(self):
        path, plan = self.plan()
        self.store.record_review(path, 's2', 'outside-managed-literal', 'other-turn')
        self.mark(path, 'keep', session='s2')
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_missing_candidate_is_displayed_as_blocked(self):
        path = self.observe()
        path.unlink()
        row = self.listed(path)
        self.assertEqual(row['state'], 'blocked')
        self.assertIsNone(row['snapshot'])

    def test_observation_replacement_revokes_marked_plan(self):
        path, plan = self.plan()
        self.store.record_review(path, 's1', 'new-observation', 't2')
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_discovery_disabled_does_not_revoke_explicit_review_or_restore(self):
        path, plan = self.plan()
        self.store.config['discover_temp'] = False
        self.store.save_config()
        mid = self.apply(plan)['quarantined'][0]
        self.store.restore(mid)
        self.assertTrue(path.exists())

    def test_pending_hook_retains_literal_and_cwd_access_for_foreign_review(self):
        path, plan = self.plan()
        self.store.hook({'hook_event_name': 'PreToolUse', 'session_id': 's2', 'turn_id': 't2',
                         'tool_use_id': 'reader', 'cwd': str(self.base / 'unrelated'),
                         'tool_input': {'path': str(path)}})
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    def test_link_replacement_between_plan_and_apply_is_refused(self):
        path, plan = self.plan()
        source = self.project / 'source.txt'
        path.rename(source)
        try:
            path.symlink_to(source)
        except OSError:
            self.skipTest('symlink unavailable')
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertEqual(source.read_text(), 'disposable rendering check')

    def test_restore_rejects_replaced_parent(self):
        path, plan = self.plan()
        mid = self.apply(plan)['quarantined'][0]
        old = self.base / 'old-parent'
        self.project.rename(old)
        self.project.mkdir()
        (old / '.codex-disk-cleanup-quarantine').rename(self.project / '.codex-disk-cleanup-quarantine')
        with self.assertRaises(c.Refused):
            self.store.restore(mid)
        self.assertFalse(path.exists())

    def test_recover_committed_move_preserves_review_authority(self):
        path, plan = self.plan()
        rename = c.os.rename
        def committed_but_interrupted(source, dest):
            rename(source, dest)
            raise OSError('process interrupted after rename')
        with patch.object(c.os, 'rename', side_effect=committed_but_interrupted):
            self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertFalse(path.exists())
        result = self.store.recover()
        self.assertEqual(result['recovered'][0]['state'], 'quarantined')
        self.store.restore(result['recovered'][0]['id'])
        self.assertTrue(path.exists())

    def test_foreign_missing_cwd_keeps_unknown_access_guard(self):
        path, plan = self.plan()
        self.store.hook({'hook_event_name': 'PreToolUse', 'session_id': 's2', 'turn_id': 't2',
                         'tool_use_id': 'reader', 'tool_input': {'path': str(path)}})
        self.assertEqual(self.apply(plan)['quarantined'], [])
        self.assertTrue(path.exists())

    @unittest.skipIf(os.name == 'nt', 'POSIX temp alias')
    def test_foreign_tmp_alias_cwd_blocks_review_inside_canonical_tmp(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            path = Path(tmp).resolve() / 'render.txt'
            path.write_text('temporary render')
            self.store.record_review(path, 's1', 'outside-managed-literal', 't1')
            self.mark(path)
            plan = self.store.review_plan('s1')
            self.store.hook({'hook_event_name': 'PreToolUse', 'session_id': 's2', 'turn_id': 't2',
                             'tool_use_id': 'reader', 'cwd': '/tmp',
                             'tool_input': {'command': 'python helper.py'}})
            self.assertEqual(self.apply(plan)['quarantined'], [])
            self.assertTrue(path.exists())


if __name__ == '__main__':
    unittest.main()
