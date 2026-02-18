"""GPU buffer register tests.

Tests setGPUBuffer / getGPUBuffer built-in functions.
The GPU object is created but the display is never initialized,
so the tests run fully headless while still having a live GPU register.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from tests.test_mcl_comprehensive import compile_and_run_mcl
except ModuleNotFoundError:
    from test_mcl_comprehensive import compile_and_run_mcl


def run_mcl_gpu(code: str, max_cycles: int = 10000) -> int:
    """Compile and run MCL code with a headless GPU instance."""
    result, error = compile_and_run_mcl(code, max_cycles=max_cycles, enable_gpu=True)
    if error:
        raise AssertionError(f"VM/Compiler error: {error}")
    return result


class TestGPUBuffer(unittest.TestCase):
    """Tests for GPU buffer control register via setGPUBuffer / getGPUBuffer."""

    def test_set_edit_buffer(self):
        """setGPUBuffer(0, 1) sets the edit buffer to 1 and getGPUBuffer(0) returns 1."""
        code = '''
        function main() {
            setGPUBuffer(0, 1); // Set edit buffer to 1
            var val: int = getGPUBuffer(0);
            return val;
        }
        '''
        self.assertEqual(run_mcl_gpu(code), 1)

    def test_set_display_buffer(self):
        """setGPUBuffer(1, 1) sets the display buffer to 1 and getGPUBuffer(1) returns 1."""
        code = '''
        function main() {
            setGPUBuffer(1, 1); // Set display buffer to 1
            var val: int = getGPUBuffer(1);
            return val;
        }
        '''
        self.assertEqual(run_mcl_gpu(code), 1)

    def test_edit_buffer_reset(self):
        """setGPUBuffer(0, 0) clears the edit buffer and getGPUBuffer(0) returns 0."""
        code = '''
        function main() {
            setGPUBuffer(0, 0); // Set edit buffer to 0
            var val: int = getGPUBuffer(0);
            return val;
        }
        '''
        self.assertEqual(run_mcl_gpu(code), 0)

    def test_display_buffer_reset(self):
        """setGPUBuffer(1, 0) clears the display buffer and getGPUBuffer(1) returns 0."""
        code = '''
        function main() {
            setGPUBuffer(1, 0); // Set display buffer to 0
            var val: int = getGPUBuffer(1);
            return val;
        }
        '''
        self.assertEqual(run_mcl_gpu(code), 0)

    def test_edit_does_not_affect_display(self):
        """Setting edit buffer does not change display buffer."""
        code = '''
        function main() {
            setGPUBuffer(1, 1); // display = 1
            setGPUBuffer(0, 1); // edit   = 1
            var val: int = getGPUBuffer(1); // display should still be 1
            return val;
        }
        '''
        self.assertEqual(run_mcl_gpu(code), 1)

    def test_display_does_not_affect_edit(self):
        """Setting display buffer does not change edit buffer."""
        code = '''
        function main() {
            setGPUBuffer(0, 1); // edit    = 1
            setGPUBuffer(1, 1); // display = 1
            var val: int = getGPUBuffer(0); // edit should still be 1
            return val;
        }
        '''
        self.assertEqual(run_mcl_gpu(code), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
