import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cleanup

class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_cleanup(self, text, config=None):
        source, config_path, output = self.root / 'input.csv', self.root / 'config.json', self.root / 'output'
        source.write_bytes(text.encode('utf-8'))
        config_path.write_text(json.dumps(config or {'delimiter': ','}), encoding='utf-8')
        return cleanup.clean_csv(source, config_path, output), output

    def rows(self, path):
        with path.open(encoding='utf-8-sig', newline='') as handle:
            return list(csv.reader(handle))

    def test_bom_multiline_leading_zeroes_and_each_change(self):
        text = '\ufeffid;name;email;notes\r\n001; Alice ; A@EXAMPLE.TEST ;"first\r\nsecond"\r\n0002;Bob;b@example.test;=1+1\r\n'
        config = {'trim_columns': ['name', 'email'], 'case_columns': {'email': 'lower'}, 'excel_safe': True}
        summary, output = self.run_cleanup(text, config)
        self.assertEqual(self.rows(output / 'clean.csv')[1], ['001', 'Alice', 'a@example.test', 'first\r\nsecond'])
        self.assertEqual(summary['source']['delimiter'], ';')
        self.assertEqual(summary['source']['sha256'], hashlib.sha256(text.encode()).hexdigest())
        changes = self.rows(output / 'changes.csv')
        self.assertEqual(len(changes) - 1, 3)
        self.assertEqual(summary['changed_cells'], 2)
        self.assertEqual(changes[-1][3:], ['A@EXAMPLE.TEST', 'a@example.test', 'lower'])
        review = self.rows(output / 'review.csv')[1]
        self.assertEqual(review[-1], '=1+1')
        self.assertEqual(review[:2], ['2', '4'])
        self.assertEqual(self.rows(output / 'excel-safe' / 'review.csv')[1][-1], "'=1+1")

    def test_duplicates_conflicts_dates_and_missing_values_reconcile(self):
        text = 'id,name,date\n001,Alice,2026-01-02\n001, Alice ,2026-01-02\n002,Bob,2026-02-29\n003,Carol,2026-03-01\n003,Changed,2026-03-01\n004,,2026-04-01\n005,Eve,03/04/2026\n006,Frank,2026-1-01\n'
        config = {'delimiter': ',', 'trim_columns': ['name'], 'required_columns': ['name'], 'key_columns': ['id'], 'date_columns': {'date': ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']}}
        summary, output = self.run_cleanup(text, config)
        self.assertEqual((summary['clean_rows'], summary['review_rows'], summary['duplicates_rows']), (1, 6, 1))
        self.assertEqual(summary['reconciliation'], {'input_rows': 8, 'partition_rows': 8, 'balanced': True, 'verified_output_rows': 8, 'cells_round_trip_verified': True})
        self.assertEqual(summary['conflicting_key_groups'], 1)
        duplicate = self.rows(output / 'duplicates.csv')[1]
        self.assertEqual((duplicate[0], duplicate[3]), ('2', '1'))
        issues = [row[2] for row in self.rows(output / 'review.csv')[1:]]
        self.assertEqual(sum('conflicting_key:id' in issue for issue in issues), 2)
        self.assertEqual(sum('invalid_date:date' in issue for issue in issues), 2)
        self.assertTrue(any('ambiguous_date:date' in issue for issue in issues))
        self.assertTrue(any('missing_required:name' in issue for issue in issues))
        self.assertEqual([int(row[0]) for row in self.rows(output / 'row-audit.csv')[1:]], list(range(1, 9)))

    def test_unconfigured_cells_are_not_normalized(self):
        summary, output = self.run_cleanup('id,value,date\n000001, FullＷidth ,2026/01/02\n')
        self.assertEqual(self.rows(output / 'clean.csv')[1], ['000001', ' FullＷidth ', '2026/01/02'])
        self.assertEqual(summary['change_events'], 0)

    def test_invalid_duplicates_keep_issues(self):
        summary, output = self.run_cleanup('id,date\n001,bad\n001,bad\n', {'delimiter': ',', 'date_columns': {'date': ['%Y-%m-%d']}})
        self.assertEqual((summary['review_rows'], summary['duplicates_rows']), (1, 1))
        row = self.rows(output / 'duplicates.csv')[1]
        self.assertEqual(row[3], '1')
        self.assertIn('invalid_date', row[2])

    def test_bad_headers_width_and_quotes_rejected_before_output(self):
        for i, text in enumerate(['id,id\n1,2\n', 'id,name\n1\n', 'id,name\n1,2,3\n', 'id,name\n1,"unfinished\n']):
            with self.subTest(text=text):
                source, config, output = self.root / f'in{i}.csv', self.root / f'c{i}.json', self.root / f'out{i}'
                source.write_text(text)
                config.write_text('{"delimiter": ","}')
                with self.assertRaises(cleanup.CleanupError):
                    cleanup.clean_csv(source, config, output)
                self.assertFalse(output.exists())

    def test_invalid_utf8_and_existing_outputs_rejected(self):
        source, config, output = self.root / 'input.csv', self.root / 'config.json', self.root / 'result'
        config.write_text('{}')
        source.write_bytes(b'id\n\xff\n')
        with self.assertRaisesRegex(cleanup.CleanupError, 'UTF-8'):
            cleanup.clean_csv(source, config, output)
        source.write_text('id\n001\n')
        output.mkdir()
        (output / 'keep.txt').write_text('unchanged')
        with self.assertRaisesRegex(cleanup.CleanupError, 'already exists'):
            cleanup.clean_csv(source, config, output)
        self.assertEqual((output / 'keep.txt').read_text(), 'unchanged')

    def test_row_and_column_service_limits(self):
        with patch.object(cleanup, 'MAX_ROWS', 1):
            with self.assertRaisesRegex(cleanup.CleanupError, 'at most 1 data rows'):
                self.run_cleanup('id\n001\n002\n')
        with patch.object(cleanup, 'MAX_COLUMNS', 1):
            with self.assertRaisesRegex(cleanup.CleanupError, 'at most 1 columns'):
                self.run_cleanup('id,name\n001,Alice\n')
        self.assertFalse((self.root / 'output').exists())

    def test_metadata_header_collision_and_safe_audit_copies(self):
        summary, output = self.run_cleanup('__audit_source_row,value\n001,  =1\n', {'trim_columns': ['value'], 'excel_safe': True})
        self.assertEqual(summary['audit_metadata_prefix'], '___audit_')
        headers = self.rows(output / 'review.csv')[0]
        self.assertEqual(len(headers), len(set(headers)))
        self.assertEqual(self.rows(output / 'changes.csv')[1][3:5], ['  =1', '=1'])
        self.assertEqual(self.rows(output / 'excel-safe' / 'changes.csv')[1][3:5], ["'  =1", "'=1"])
        for value in ['=1', '+cmd', '-1', '@SUM(A1)', '  =1', '\ttext', '\rtext', '\ntext']:
            self.assertTrue(cleanup.formula_risk(value))
        self.assertFalse(cleanup.formula_risk('001'))

    def test_bare_carriage_returns_round_trip_in_data_and_audit(self):
        summary, output = self.run_cleanup('id,name,note\r\n001,"Alice\r","left\rright"\r\n', {'trim_columns': ['name'], 'excel_safe': True})
        self.assertEqual(self.rows(output / 'clean.csv')[1], ['001', 'Alice', 'left\rright'])
        self.assertEqual(self.rows(output / 'changes.csv')[1][3], 'Alice\r')
        self.assertEqual(summary['output_rows']['clean.csv'], 1)
        self.assertEqual(summary['reconciliation']['verified_output_rows'], 1)
        self.assertTrue(summary['reconciliation']['cells_round_trip_verified'])

    def test_config_snapshot_and_all_output_hashes(self):
        source, config, output = self.root / 'snapshot.csv', self.root / 'snapshot.json', self.root / 'snapshot-output'
        source.write_text('id,name\n001, Alice \n')
        original_config = b'{"trim_columns": ["name"], "excel_safe": true}'
        config.write_bytes(original_config)
        original_read = Path.read_bytes
        reads = []
        def snapshot_read(path):
            if path == config:
                reads.append(path)
                return original_config if len(reads) == 1 else b'{}'
            return original_read(path)
        with patch.object(Path, 'read_bytes', snapshot_read):
            summary = cleanup.clean_csv(source, config, output)
        self.assertEqual(len(reads), 1)
        self.assertEqual(summary['config_sha256'], hashlib.sha256(original_config).hexdigest())
        self.assertEqual(summary['change_events'], 1)
        self.assertEqual(len(summary['output_sha256']), 10)
        for filename, digest in summary['output_sha256'].items():
            self.assertEqual(hashlib.sha256((output / filename).read_bytes()).hexdigest(), digest)

    def test_config_typos_implicit_dates_and_unknown_columns_rejected(self):
        for config in [{'trim_column': ['id']}, {'excel_safe': 'yes'}, {'date_columns': {'date': ['%x']}}, {'trim_columns': ['missing']}]:
            with self.subTest(config=config):
                with self.assertRaises(cleanup.CleanupError):
                    self.run_cleanup('id,date\n001,01/02/26\n', config)

if __name__ == '__main__':
    unittest.main()
