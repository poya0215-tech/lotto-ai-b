import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from lotto_data import (validate_record, create_draw_table, save_records, load_records,
                        parse_csv, frequencies, update_official)

SAMPLE = dict(draw_no=1, draw_date='2002-12-07', n1=10, n2=23, n3=29,
              n4=33, n5=37, n6=40, bonus=16)

class DataTests(unittest.TestCase):
    def test_valid_record(self):
        self.assertEqual(validate_record(SAMPLE)['n1'], 10)

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            validate_record({**SAMPLE, 'bonus': 10})

    def test_roundtrip_and_frequency(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'db.sqlite'
            create_draw_table(path)
            save_records(path, [SAMPLE], 'test')
            save_records(path, [SAMPLE], 'test')
            rows = load_records(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(frequencies(rows)[10], 1)
            self.assertEqual(frequencies(rows)[16], 0)

    def test_csv(self):
        csv_data = 'draw_no,draw_date,n1,n2,n3,n4,n5,n6,bonus\n1,2002-12-07,10,23,29,33,37,40,16\n'
        self.assertEqual(len(parse_csv(csv_data)), 1)

    def test_incremental_fetch(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'db.sqlite'
            create_draw_table(path)
            with patch('lotto_data.fetch_official_draw', side_effect=[SAMPLE, None]) as mocked:
                self.assertEqual(update_official(path, 3, 0), 1)
                self.assertEqual(mocked.call_count, 2)

if __name__ == '__main__':
    unittest.main()
