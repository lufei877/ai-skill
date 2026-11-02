import sqlite3
import unittest

from gateway import invoice


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.execute("CREATE TABLE invoices (id INTEGER, owner_id INTEGER, amount INTEGER)")
        self.connection.execute("INSERT INTO invoices VALUES (1, 7, 100)")

    def test_owner_can_read(self):
        self.assertEqual(invoice(self.connection, 7, 1)["amount"], 100)

    def test_other_user_cannot_read(self):
        with self.assertRaises(LookupError):
            invoice(self.connection, 8, 1)

    def test_query_input_is_not_sql(self):
        with self.assertRaises(LookupError):
            invoice(self.connection, 7, "1 OR 1=1")
