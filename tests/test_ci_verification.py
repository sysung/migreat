

import unittest


class CiVerificationTest(unittest.TestCase):
    def test_intentional_failure(self):
        self.fail("Intentional CI verification failure")
