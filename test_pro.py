import unittest
from pro_stats import analyze, tests
from test_data import SAMPLE
class ProTests(unittest.TestCase):
    def test_counts(self):
        r=analyze([SAMPLE,{**SAMPLE,'draw_no':2}]); self.assertEqual(r['freq']['전체'].sum(),12); self.assertEqual(r['overlap'][6],1); self.assertEqual(r['pairs'].iloc[0]['횟수'],2)
    def test_gap(self):
        r=analyze([SAMPLE,{**SAMPLE,'draw_no':3}]); self.assertTrue(r['overlap'].empty); self.assertIsNone(tests(r,19)['인접 회차 겹침 p값'])
    def test_null(self):
        r=analyze([SAMPLE,{**SAMPLE,'draw_no':2}]); p=tests(r,19); self.assertTrue(0<p['균등성 p값']<=1); self.assertTrue(0<p['인접 회차 겹침 p값']<=1)
