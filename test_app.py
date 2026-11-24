import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app


class GeneratorTests(unittest.TestCase):
    def test_valid_unique_tickets(self):
        tickets = app.generate_tickets(20, None, True)
        self.assertEqual(len(tickets), 20)
        self.assertEqual(len(set(tickets)), 20)
        for ticket in tickets:
            self.assertEqual(len(ticket), 6)
            self.assertEqual(len(set(ticket)), 6)
            self.assertTrue(all(1 <= n <= 45 for n in ticket))

    def test_odd_filter(self):
        for odd in (2, 3, 4):
            tickets = app.generate_tickets(5, odd, False)
            self.assertTrue(all(sum(n % 2 for n in t) == odd for t in tickets))

    def test_database_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(app, "DB_PATH", Path(temp) / "test.db"):
                app.initialize_database()
                app.save_tickets([(1, 2, 3, 4, 5, 6)], "test")
                history = app.load_history()
                self.assertEqual(len(history), 1)
                self.assertEqual(history.iloc[0]["numbers"], "1,2,3,4,5,6")


if __name__ == "__main__":
    unittest.main()
