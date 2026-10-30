"""Offline pipeline tests. Pi inference and HTTP collection are always mocked."""
import argparse
import csv
import importlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from . import classify as app
except ImportError:
    import classify as app


class Rules(unittest.TestCase):
    def test_all_numeric_combinations(self):
        expected = [[3, 3, 3, 3], [3, 2, 2, 2], [3, 2, 2, 1]]
        for recipe in range(3):
            for observed in range(2):
                for intended in range(2):
                    row = {'recipe': recipe, 'observed': observed, 'expected': intended,
                           'target': 'single', 'external': 'no'}
                    self.assertEqual(app.grade(row), expected[recipe][observed * 2 + intended])

    def test_pending_gate(self):
        row = {'recipe': 2, 'observed': 1, 'expected': 1, 'target': 'single', 'external': 'no'}
        for key, value in [('target', 'multiple'), ('target', 'unclear'), ('external', 'yes'),
                           ('external', 'unclear'), ('recipe', None), ('observed', None), ('expected', None)]:
            self.assertEqual(app.grade({**row, key: value}), 'pending')

    def test_deduplication_and_conflicting_versions(self):
        row = {'url': 'https://api.github.com/repos/a/b/issues/1', 'issue_title': 'Problem', 'issue_body': 'Full text'}
        first = app.normalize(row)
        self.assertEqual(first['project'], 'a/b')
        self.assertEqual(first['record_id'], app.normalize({**row, 'id': 'another source ID'})['record_id'])
        self.assertNotEqual(first['record_id'], app.normalize({**row, 'issue_body': 'Different version'})['record_id'])
        with self.assertRaises(ValueError):
            app.normalize({**row, 'title': 'Contradicts issue_title'})

    def test_null_source_id_falls_back_to_bug_id(self):
        row = app.normalize({'url': 'https://example.org/1', 'source_id': None, 'bug_id': 'B1'})
        self.assertEqual(row['source_id'], 'B1')

    def test_scope_is_required(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder) / 'missing.jsonl'
            with self.assertRaises(SystemExit):
                app.main(['run', str(missing), '--out', str(Path(folder) / 'run')])


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'input.jsonl'
        self.calls = []

    def write(self, rows):
        self.path.write_text(''.join(json.dumps(x) + '\n' for x in rows))

    def args(self, **changes):
        return argparse.Namespace(input=self.path, out=self.root / 'run', limit=100,
                                  workers=2, retry_failed=changes.get('retry_failed', False))

    def infer(self, stage, rows, directory):
        self.calls.append((stage, [r['record_id'] for r in rows]))
        if stage == 'type':
            categories = {'Question': 'no_bug', 'Change': 'change_submission', 'Unclear': 'unclear'}
            return [{'record_id': r['record_id'], 'category': categories.get(r['title'], 'bug')} for r in rows]
        return [{'record_id': r['record_id'], 'recipe': 0 if r['title'] == 'Vague' else 2,
                 'observed': 1, 'expected': 1, 'target': 'single',
                 'external': 'yes' if r['title'] == 'Evidence needed' else 'no'} for r in rows]

    def run_mocked(self, args=None, infer=None):
        with patch.object(app.pi_runner, 'check', return_value=[]), \
                patch.object(app.pi_runner, 'infer', side_effect=infer or self.infer), \
                patch.object(app.evidence, 'collect', return_value={'evidence': [], 'files': [], 'optional_files': []}):
            app.run(args or self.args())

    def test_two_stages_dedup_resume_and_export(self):
        titles = ['Crash', 'Question', 'Change', 'Unclear', 'Vague', 'Evidence needed']
        rows = [{'url': f'https://github.com/a/b/issues/{i}', 'title': title, 'body': 'Original body'}
                for i, title in enumerate(titles, 1)]
        self.write(rows + [rows[0]])
        self.run_mocked()
        directory = self.root / 'run'
        labels = [json.loads(x) for x in (directory / 'labels.jsonl').read_text().splitlines()]
        self.assertEqual(len(labels), 6)
        self.assertEqual(sum(x['category'] == 'bug' for x in labels), 3)
        self.assertEqual(sum(x['vagueness'] == 'pending' for x in labels), 1)
        self.assertEqual(sum(x['vagueness'] == 3 for x in labels), 1)
        self.assertEqual(sum(len(ids) for stage, ids in self.calls if stage == 'grade'), 3)
        original_calls = list(self.calls)
        self.run_mocked()
        self.assertEqual(self.calls, original_calls)
        self.assertEqual(json.loads((directory / 'summary.json').read_text())['failed_or_unfinished'], 0)

    def test_all_source_id_aliases_are_preserved(self):
        row = {'url': 'https://example.org/1', 'title': 'Crash', 'body': 'Text'}
        self.write([{**row, 'source_id': 'first'}, {**row, 'source_id': 'second'}])
        self.run_mocked()
        with (self.root / 'run/records.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual({r['source_id'] for r in rows}, {'first', 'second'})
        self.assertEqual(len({r['record_id'] for r in rows}), 1)
        self.assertEqual(len((self.root / 'run/labels.jsonl').read_text().splitlines()), 1)

    def test_failure_does_not_rerun_type_or_invent_pending(self):
        self.write([{'url': 'https://github.com/a/b/issues/1', 'title': 'Crash', 'body': 'Full text'}])
        def fail(stage, rows, directory):
            if stage == 'grade':
                self.calls.append(('grade_failed', [r['record_id'] for r in rows]))
                raise RuntimeError('simulated quota interruption')
            return self.infer(stage, rows, directory)
        with self.assertRaises(RuntimeError):
            self.run_mocked(infer=fail)
        self.assertEqual((self.root / 'run/labels.jsonl').read_text(), '')
        with self.assertRaises(RuntimeError):
            self.run_mocked()
        self.run_mocked(self.args(retry_failed=True))
        self.assertEqual(sum(stage == 'type' for stage, _ in self.calls), 1)
        self.assertEqual(len((self.root / 'run/labels.jsonl').read_text().splitlines()), 1)

    def test_changed_input_is_not_mixed_into_old_output(self):
        self.write([{'url': 'https://example.org/1', 'title': 'Crash', 'body': 'text'}])
        self.run_mocked()
        self.write([{'url': 'https://example.org/1', 'title': 'Crash', 'body': 'changed'}])
        with self.assertRaises(ValueError):
            self.run_mocked()

    @unittest.skipUnless(importlib.util.find_spec('duckdb'), 'DuckDB is optional for JSONL')
    def test_raw_and_catalog_parquet_aliases(self):
        duckdb = importlib.import_module('duckdb')
        db = duckdb.connect()
        try:
            first, second = self.root / 'raw.parquet', self.root / 'canonical.parquet'
            db.execute('CREATE TABLE raw(url VARCHAR, issue_title VARCHAR, issue_body VARCHAR)')
            db.execute("INSERT INTO raw VALUES ('https://api.github.com/repos/a/b/issues/1','Bug','original')")
            db.sql('SELECT * FROM raw').write_parquet(str(first))
            db.execute('CREATE TABLE canonical(url VARCHAR,title VARCHAR,body VARCHAR)')
            db.execute("INSERT INTO canonical VALUES ('https://api.github.com/repos/a/b/issues/1','Bug','different')")
            db.sql('SELECT * FROM canonical').write_parquet(str(second))
            rows = list(app.read_input([first, second]))
            self.assertEqual([r['body'] for r in rows], ['original', 'different'])
            self.assertNotEqual(rows[0]['record_id'], rows[1]['record_id'])
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
