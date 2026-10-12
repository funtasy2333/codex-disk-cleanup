import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_cleanup import c, SCRIPT


class GeneratedImagePreviewTests(unittest.TestCase):
    SESSION = '00000000-0000-4000-8000-000000000001'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.home = self.base / 'codex-home'
        self.root = self.home / 'generated_images' / self.SESSION
        self.root.mkdir(parents=True)
        self.copies = self.base / 'project' / 'sources'
        self.copies.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def preview(self, copies=None):
        return c.generated_preview(self.SESSION, [self.copies] if copies is None else copies,
                                   codex_home=self.home)

    def test_identical_copy_is_review_candidate_not_a_cleanup_plan(self):
        source = self.root / 'exec-a.png'
        source.write_bytes(b'image fixture')
        copy = self.copies / 'retained.png'
        copy.write_bytes(source.read_bytes())
        result = self.preview()
        self.assertTrue(result['preview_only'])
        self.assertNotIn('plan_id', result)
        self.assertEqual(result['items'][0]['matching_copies'][0]['path'], str(copy))
        self.assertEqual(result['verified_duplicate_bytes'], source.stat().st_size)
        self.assertTrue(source.exists())
        self.assertFalse((self.home / 'plugins').exists())

    def test_different_or_absent_copy_is_not_verified(self):
        (self.root / 'exec-a.png').write_bytes(b'original')
        (self.copies / 'different.png').write_bytes(b'different')
        result = self.preview()
        self.assertEqual(result['items'][0]['classification'], 'no-copy-verified')
        self.assertEqual(result['verified_duplicate_bytes'], 0)

    def test_no_copy_directory_does_not_invent_evidence(self):
        (self.root / 'exec-a.png').write_bytes(b'original')
        self.assertEqual(self.preview([])['items'][0]['matching_copies'], [])

    def test_missing_session_does_not_initialize_state_or_directories(self):
        missing = '00000000-0000-4000-8000-000000000002'
        result = c.generated_preview(missing, [], codex_home=self.home)
        self.assertFalse(result['available'])
        self.assertFalse((self.home / 'generated_images' / missing).exists())
        self.assertFalse((self.home / 'plugins').exists())

    def test_uuid_and_absolute_home_required(self):
        for session in ['../auth', '', 'all', self.SESSION + '/..']:
            with self.subTest(session=session), self.assertRaises(c.Refused):
                c.generated_preview(session, [], codex_home=self.home)
        with self.assertRaises(c.Refused):
            c.generated_preview(self.SESSION, [], codex_home=Path('relative'))

    def test_copy_inside_codex_or_containing_codex_refused(self):
        for root in [self.root, self.home, self.base]:
            with self.subTest(root=root), self.assertRaises(c.Refused):
                self.preview([root])

    def test_other_sessions_not_scanned(self):
        (self.root / 'exec-a.png').write_bytes(b'ours')
        other = self.home / 'generated_images' / 'another-session'
        other.mkdir()
        (other / 'exec-b.png').write_bytes(b'other')
        result = self.preview()
        self.assertEqual(len(result['items']), 1)
        self.assertEqual(result['items'][0]['path'], str(self.root / 'exec-a.png'))

    def test_links_hardlinks_and_non_images_not_candidates(self):
        victim = self.copies / 'source.png'
        victim.write_bytes(b'original')
        import os
        os.link(victim, self.root / 'hardlink.png')
        (self.root / 'state.sqlite3').write_bytes(b'database')
        try:
            (self.root / 'symlink.png').symlink_to(victim)
        except OSError:
            pass
        result = self.preview()
        self.assertEqual(result['items'], [])
        self.assertTrue(victim.exists())

    def test_scan_budget_shared_across_source_and_copies(self):
        (self.root / 'a.png').write_bytes(b'a')
        (self.copies / 'b.png').write_bytes(b'a')
        (self.copies / 'c.png').write_bytes(b'a')
        with patch.object(c, 'MAX_ITEMS', 2), self.assertRaises(c.Refused):
            self.preview()

    def test_cli_preview_does_not_create_data_and_rejects_apply(self):
        (self.root / 'a.png').write_bytes(b'a')
        (self.copies / 'b.png').write_bytes(b'a')
        data = self.base / 'plugin-data-not-created'
        command = [sys.executable, str(SCRIPT), '--data', str(data), 'generated-preview',
                   '--session', self.SESSION, '--codex-home', str(self.home),
                   '--copy-root', str(self.copies)]
        proc = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['verified_duplicate_bytes'], 1)
        self.assertFalse(data.exists())
        proc = subprocess.run([*command, '--apply', 'anything', '--yes'], capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue((self.root / 'a.png').exists())
