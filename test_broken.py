import unittest
import broken_module

class TestBrokenModule(unittest.TestCase):
    def test_computation(self):
        try:
            result = broken_module.execute_core_computation()
            self.assertEqual(result, 42)
        except AssertionError as e:
            self.fail(f"Math core corrupt: {e}")
        except Exception as e:
            self.fail(f"Unexpected error: {e}")

if __name__ == "__main__":
    unittest.main()
