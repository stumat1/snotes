"""Tests for sNotesv2 core logic.

Runs headless — no display required. tkinter is stubbed before import.
Run with:  python -m pytest tests/
"""
import sys
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub out tkinter so tests run headless (no display required)
# ---------------------------------------------------------------------------
for _mod in ('tkinter', 'tkinter.ttk', 'tkinter.messagebox',
             'tkinter.font', 'tkinter.filedialog', 'tkinter.simpledialog'):
    sys.modules[_mod] = MagicMock()

import snotes  # noqa: E402  (must come after the stubs)


def _bare_app(tmp_path: Path) -> snotes.NoteApp:
    """Instantiate NoteApp bypassing __init__ — no tkinter calls needed."""
    app = object.__new__(snotes.NoteApp)
    app.data_dir = tmp_path
    app.notes_file = tmp_path / 'notes.json'
    app.config_file = tmp_path / 'config.json'
    app.notes = {}
    app.config = {}
    return app


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.app = _bare_app(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_save_load_notes_roundtrip(self):
        self.app.notes = {
            'abc123': {
                'title': 'Hello', 'content': 'World',
                'created': '2026-01-01T10:00:00', 'modified': '2026-01-01T10:00:00',
            }
        }
        self.app.save_notes()
        self.app.notes = {}
        loaded = self.app.load_notes()
        self.assertEqual(loaded['abc123']['title'], 'Hello')
        self.assertEqual(loaded['abc123']['content'], 'World')

    def test_save_notes_no_tmp_residue(self):
        """Atomic save must clean up the .tmp file on success."""
        self.app.notes = {'x': {'title': 'T', 'content': 'C', 'created': '', 'modified': ''}}
        self.app.save_notes()
        self.assertFalse(self.app.notes_file.with_suffix('.tmp').exists())
        self.assertTrue(self.app.notes_file.exists())

    def test_save_notes_does_not_corrupt_on_replace_failure(self):
        """If the atomic rename fails, the original notes file must be untouched."""
        original = {'orig': {'title': 'Safe', 'content': 'Data', 'created': '', 'modified': ''}}
        self.app.notes = original
        self.app.save_notes()

        self.app.notes = {'new': {'title': 'Should not appear', 'content': '', 'created': '', 'modified': ''}}
        with patch.object(Path, 'replace', side_effect=OSError("disk full")):
            self.app.save_notes()

        saved = json.loads(self.app.notes_file.read_text(encoding='utf-8'))
        self.assertIn('orig', saved)
        self.assertNotIn('new', saved)

    def test_load_notes_returns_empty_when_file_missing(self):
        loaded = self.app.load_notes()
        self.assertEqual(loaded, {})

    def test_save_load_config_roundtrip(self):
        self.app.config = {'editor_font_size': 14, 'sort_mode': 'alpha'}
        self.app.save_config()
        self.app.config = {}
        loaded = self.app.load_config()
        self.assertEqual(loaded['editor_font_size'], 14)
        self.assertEqual(loaded['sort_mode'], 'alpha')

    def test_save_config_no_tmp_residue(self):
        self.app.config = {'key': 'value'}
        self.app.save_config()
        self.assertFalse(self.app.config_file.with_suffix('.tmp').exists())

    def test_notes_file_is_valid_json_after_save(self):
        self.app.notes = {'id1': {'title': 'A', 'content': 'B', 'created': '', 'modified': ''}}
        self.app.save_notes()
        raw = self.app.notes_file.read_text(encoding='utf-8')
        parsed = json.loads(raw)  # must not raise
        self.assertIn('id1', parsed)


# ---------------------------------------------------------------------------
# Note ID uniqueness
# ---------------------------------------------------------------------------

class TestNoteIds(unittest.TestCase):

    def test_no_collision_across_rapid_creations(self):
        """UUIDs must be unique even when generated in rapid succession."""
        ids = [snotes.uuid.uuid4().hex for _ in range(10_000)]
        self.assertEqual(len(set(ids)), 10_000)

    def test_id_format_is_hex_not_timestamp(self):
        """Note IDs must be 32-char hex strings, not legacy timestamp strings."""
        import re
        note_id = snotes.uuid.uuid4().hex
        self.assertRegex(note_id, r'^[0-9a-f]{32}$')
        self.assertNotRegex(note_id, r'^\d{8}_\d{6}$')


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class TestExportAllNotes(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.app = _bare_app(Path(self._tmp.name))
        self.app.status_bar = MagicMock()
        self.app.root = MagicMock()
        self.app.notes = {
            'id1': {'title': 'Note One', 'content': 'Content one', 'created': '', 'modified': ''},
            'id2': {'title': 'Note Two', 'content': 'Content two', 'created': '', 'modified': ''},
            'id3': {'title': 'Empty Note', 'content': '',           'created': '', 'modified': ''},
        }

    def tearDown(self):
        self._tmp.cleanup()

    def _export_dir(self):
        d = Path(self._tmp.name) / 'export'
        d.mkdir()
        snotes.filedialog.askdirectory.return_value = str(d)
        return d

    def test_exports_only_non_empty_notes(self):
        export_dir = self._export_dir()
        self.app.export_all_notes()
        self.assertEqual(len(list(export_dir.glob('*.txt'))), 2)

    def test_status_bar_shows_correct_count_on_success(self):
        self._export_dir()
        self.app.export_all_notes()
        text = self.app.status_bar.config.call_args[1]['text']
        self.assertIn('2', text)
        self.assertNotIn('failed', text)

    def test_status_bar_reports_failures(self):
        self._export_dir()
        with patch.object(Path, 'write_text', side_effect=PermissionError("denied")):
            self.app.export_all_notes()
        text = self.app.status_bar.config.call_args[1]['text']
        self.assertIn('failed', text)

    def test_no_export_when_cancelled(self):
        snotes.filedialog.askdirectory.return_value = ''  # user cancelled
        self.app.export_all_notes()
        self.app.status_bar.config.assert_not_called()


# ---------------------------------------------------------------------------
# _time_ago
# ---------------------------------------------------------------------------

class TestTimeAgo(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.app = _bare_app(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _iso(self, delta: timedelta) -> str:
        return (datetime.now() - delta).isoformat()

    def test_just_now(self):
        self.assertEqual(self.app._time_ago(self._iso(timedelta(seconds=30))), 'just now')

    def test_minutes_ago(self):
        self.assertIn('minute', self.app._time_ago(self._iso(timedelta(minutes=5))))

    def test_hours_ago(self):
        self.assertIn('hour', self.app._time_ago(self._iso(timedelta(hours=3))))

    def test_days_ago(self):
        self.assertIn('day', self.app._time_ago(self._iso(timedelta(days=2))))

    def test_older_date_no_platform_crash(self):
        """%#d was Windows-only and raised ValueError on other platforms — must not crash."""
        result = self.app._time_ago(self._iso(timedelta(days=40)))
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_older_date_contains_month_and_day(self):
        """Dates within the current year should show e.g. 'Jan 5'."""
        # Use a date guaranteed to be within the same year but > 7 days ago
        result = self.app._time_ago(self._iso(timedelta(days=30)))
        # Should contain a 3-letter month abbreviation
        import re
        self.assertRegex(result, r'[A-Z][a-z]{2}\s+\d+')

    def test_corrupt_timestamp_returns_empty_string(self):
        self.assertEqual(self.app._time_ago('not-a-date'), '')

    def test_singular_and_plural_minutes(self):
        self.assertIn('1 minute ago', self.app._time_ago(self._iso(timedelta(seconds=90))))
        self.assertIn('2 minutes ago', self.app._time_ago(self._iso(timedelta(minutes=2, seconds=30))))


if __name__ == '__main__':
    unittest.main()
