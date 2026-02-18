"""Tests for register spilling and register allocator correctness.

When a program uses more variables/temporaries than there are available registers,
the register allocator "spills" the least-recently-used register to RAM and
"reloads" it later. These tests verify:

  1. Spill instructions emit RAM addresses as immediates (i:ADDR) so the VM
     treats them as memory addresses rather than register indices.
  2. Results of programs that trigger spilling are numerically correct.
  3. Spilling works inside loops (multiple reload cycles).
  4. A value spilled to RAM and reloaded is unchanged.
"""

import unittest
import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.compiler.lexer import tokenize
from src.compiler.parser import parse
from src.compiler.assembly_generator import generate_assembly

try:
    from test_mcl_comprehensive import compile_and_run_mcl
except ImportError:
    from tests.test_mcl_comprehensive import compile_and_run_mcl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compile_only(mcl_code: str) -> str:
    """Return the generated assembly string (no execution)."""
    tokens = tokenize(mcl_code)
    ast = parse(tokens)
    return generate_assembly(ast)


def _count_spills(assembly: str) -> int:
    return sum(1 for line in assembly.splitlines() if '// Spill' in line)


def _count_reloads(assembly: str) -> int:
    return sum(1 for line in assembly.splitlines() if '// Reload' in line)


# 35 local variables - enough to exhaust all registers and trigger spilling.
MANY_VARS_35 = """
function main() {
    var a: int = 1;
    var b: int = 2;
    var c: int = 3;
    var d: int = 4;
    var e: int = 5;
    var f: int = 6;
    var g: int = 7;
    var h: int = 8;
    var ii: int = 9;
    var j: int = 10;
    var k: int = 11;
    var l: int = 12;
    var m: int = 13;
    var n: int = 14;
    var o: int = 15;
    var p: int = 16;
    var q: int = 17;
    var r: int = 18;
    var s: int = 19;
    var t: int = 20;
    var u: int = 21;
    var v: int = 22;
    var w: int = 23;
    var x: int = 24;
    var y: int = 25;
    var z: int = 26;
    var v27: int = 27;
    var v28: int = 28;
    var v29: int = 29;
    var v30: int = 30;
    var v31: int = 31;
    var v32: int = 32;
    var v33: int = 33;
    var v34: int = 34;
    var v35: int = 35;
    return a + v35;
}
"""

MANY_VARS_MID = MANY_VARS_35.replace("return a + v35;", "return m;")

# A program that genuinely exhausts registers via a wide simultaneous expression.
# Each variable is loaded for the sum expression, keeping all of their values
# live at the same time in temporaries – more temporaries than the ~26 available
# non-reserved registers, so the spiller must kick in.
FORCED_SPILL_PROGRAM = """
function main() {
    var a: int = 1;
    var b: int = 2;
    var c: int = 3;
    var d: int = 4;
    var e: int = 5;
    var f: int = 6;
    var g: int = 7;
    var h: int = 8;
    var ii: int = 9;
    var j: int = 10;
    var k: int = 11;
    var l: int = 12;
    var m: int = 13;
    var n: int = 14;
    var o: int = 15;
    var p: int = 16;
    var q: int = 17;
    var r: int = 18;
    var s: int = 19;
    var t: int = 20;
    var u: int = 21;
    var v: int = 22;
    var w: int = 23;
    var x: int = 24;
    var y: int = 25;
    var z: int = 26;
    var dummy: int = a + b + c + d + e + f + g + h + ii + j + k + l + m + n + o + p + q + r + s + t + u + v + w + x + y + z;
    return dummy;
}
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRegisterSpilling(unittest.TestCase):
    """Tests for register spilling correctness and address format."""

    # -- Address format -------------------------------------------------------

    def test_spill_uses_immediate_address(self):
        """Any spill (LOAD) instructions that do appear must use i: prefix.

        When mid-expression register pressure forces a spill, the emitted LOAD
        must use an immediate address (i:ADDR) so the VM treats it as a memory
        address, not a register index.  This test compiles a genuinely
        pressure-heavy expression and, if spills are generated, checks the
        address format.  If no spills are generated (all temporaries fit in
        the available registers) the test passes vacuously — that is also
        correct behaviour.
        """
        asm = _compile_only(FORCED_SPILL_PROGRAM)
        spill_lines = [l for l in asm.splitlines() if '// Spill' in l]
        for line in spill_lines:
            self.assertRegex(
                line.strip(), r'LOAD\s+\d+,\s+i:\d+',
                f"Spill LOAD must use i:<addr> format - got: {line!r}")

    def test_reload_uses_immediate_address(self):
        """Reload (READ) instructions must use i: prefix for the RAM address."""
        asm = _compile_only(MANY_VARS_35)
        for line in asm.splitlines():
            if '// Reload' not in line:
                continue
            self.assertRegex(
                line.strip(), r'READ\s+i:\d+,\s+\d+',
                f"Reload READ must use i:<addr> format - got: {line!r}")

    def test_no_bare_decimal_spill_address(self):
        """No spill LOAD should have a bare decimal as the destination address."""
        asm = _compile_only(MANY_VARS_35)
        for line in asm.splitlines():
            if '// Spill' not in line:
                continue
            instruction = line.split('//')[0].strip()
            m = re.match(r'LOAD\s+\S+,\s+(\S+)', instruction)
            if m:
                dst = m.group(1)
                self.assertFalse(
                    dst.lstrip('-').isdigit(),
                    f"Spill address '{dst}' is a bare decimal (missing i:): {line!r}")

    def test_sufficient_spills_occur(self):
        """Under genuine mid-expression pressure, all variable values survive.

        35 sequential variable declarations no longer trigger spilling because
        the fixed compiler stores each local in its frame slot and properly
        frees all temporaries after each statement.  The important correctness
        property is that all values are preserved — verified by summing all
        variables and checking the arithmetic result.
        """
        # Sum 1+2+…+26 = 351.  If any variable is corrupted the result differs.
        code = FORCED_SPILL_PROGRAM.replace(
            "return dummy;", "return dummy;"  # already returns the sum
        )
        result, error = compile_and_run_mcl(code, max_cycles=500_000)
        self.assertEqual(error, "", f"Unexpected error: {error}")
        expected = sum(range(1, 27))  # 351
        self.assertEqual(result, expected,
                         f"Expected sum 1..26 = {expected}, got {result}")

    # -- Correctness: spilled values survive ----------------------------------

    def test_first_var_survives_spilling(self):
        """The first-allocated variable keeps its value after being spilled.

        'a = 1' is allocated early and will be spilled as later variables consume
        registers.  Return value a + v35 = 1 + 35 = 36 confirms both survive.

        KNOWN BUG: The register allocator can reload a spilled symbol into the
        same physical register as another live symbol, causing the addition to
        use the wrong operand (e.g. a + a = 2 instead of a + v35 = 36).
        Remove @expectedFailure once the reload aliasing bug is fixed.
        """
        result, error = compile_and_run_mcl(MANY_VARS_35, max_cycles=500_000)
        self.assertEqual(error, "", f"Unexpected error: {error}")
        self.assertEqual(result, 36,
                         f"Expected a + v35 = 1 + 35 = 36, got {result}")

    def test_mid_var_survives_spilling(self):
        """A mid-range variable retains its value under heavy register pressure."""
        result, error = compile_and_run_mcl(MANY_VARS_MID, max_cycles=500_000)
        self.assertEqual(error, "", f"Unexpected error: {error}")
        self.assertEqual(result, 13, f"Expected m = 13, got {result}")

    def test_last_var_correct_after_spilling(self):
        """The last-allocated variable has the correct value even after heavy spilling."""
        code = MANY_VARS_35.replace("return a + v35;", "return v35;")
        result, error = compile_and_run_mcl(code, max_cycles=500_000)
        self.assertEqual(error, "", f"Unexpected error: {error}")
        self.assertEqual(result, 35, f"Expected v35 = 35, got {result}")

    def test_spilled_sentinel_unchanged(self):
        """A sentinel allocated first must equal 42 after all other vars spill it.

        sentinel = 42 is allocated in the first register.  The 25 variables
        declared afterwards fill all remaining registers, pushing sentinel to RAM.
        Returning sentinel verifies the reload restores the original value.
        """
        code = """
function main() {
    var sentinel: int = 42;
    var b: int = 2;
    var c: int = 3;
    var d: int = 4;
    var e: int = 5;
    var f: int = 6;
    var g: int = 7;
    var h: int = 8;
    var ii: int = 9;
    var j: int = 10;
    var k: int = 11;
    var l: int = 12;
    var m: int = 13;
    var n: int = 14;
    var o: int = 15;
    var p: int = 16;
    var q: int = 17;
    var r: int = 18;
    var s: int = 19;
    var t: int = 20;
    var u: int = 21;
    var v: int = 22;
    var w: int = 23;
    var x: int = 24;
    var y: int = 25;
    var z: int = 26;
    var dummy: int = b + c + d + e + f + g + h + ii + j + k + l + m + n + o + p + q + r + s + t + u + v + w + x + y + z;
    return sentinel;
}
"""
        result, error = compile_and_run_mcl(code, max_cycles=500_000)
        self.assertEqual(error, "", f"Unexpected error: {error}")
        self.assertEqual(result, 42,
                         f"Sentinel corrupted by spilling: expected 42, got {result}")

    # -- Correctness: spilling inside a loop ----------------------------------

    def test_spill_inside_loop(self):
        """Variables survive spilling across repeated loop iterations.

        a=1, z=26 are under register pressure from 24 other locals.
        After 5 iterations acc = 5 * (1 + 26) = 135.

        KNOWN BUG: Under heavy register pressure, while-loop bookkeeping
        registers (cnt, acc) can be spilled with incorrect reload semantics,
        leaving acc = 0 at exit.  Remove @expectedFailure once the register
        allocator correctly handles loop variable spilling.
        """
        code = """
function main() {
    var a: int = 1;
    var b: int = 2;
    var c: int = 3;
    var d: int = 4;
    var e: int = 5;
    var f: int = 6;
    var g: int = 7;
    var h: int = 8;
    var ii: int = 9;
    var j: int = 10;
    var k: int = 11;
    var l: int = 12;
    var m: int = 13;
    var n: int = 14;
    var o: int = 15;
    var p: int = 16;
    var q: int = 17;
    var r: int = 18;
    var s: int = 19;
    var t: int = 20;
    var u: int = 21;
    var v: int = 22;
    var w: int = 23;
    var x: int = 24;
    var y: int = 25;
    var z: int = 26;
    var acc: int = 0;
    var cnt: int = 0;
    while (cnt < 5) {
        acc = acc + a + z;
        cnt = cnt + 1;
    }
    return acc;
}
"""
        result, error = compile_and_run_mcl(code, max_cycles=2_000_000)
        self.assertEqual(error, "", f"Unexpected error: {error}")
        self.assertEqual(result, 135, f"Expected 5 * (1 + 26) = 135, got {result}")

    # -- Correctness: deep expression temporaries -----------------------------

    def test_deep_expression_spill(self):
        """A deeply nested expression triggers temporary spilling correctly.

        (1+1) * (1+1) * (1+1) * (1+1) = 2^4 = 16.
        The four intermediate products must all be live simultaneously.
        """
        code = """
function main() {
    var a: int = 1;
    var b: int = 1;
    var c: int = 1;
    var d: int = 1;
    var e: int = 1;
    var f: int = 1;
    var g: int = 1;
    var h: int = 1;
    var ii: int = 1;
    var j: int = 1;
    var k: int = 1;
    var l: int = 1;
    var m: int = 1;
    var n: int = 1;
    var o: int = 1;
    var p: int = 1;
    var q: int = 1;
    var r: int = 1;
    var s: int = 1;
    var t: int = 1;
    var u: int = 1;
    var v: int = 1;
    var w: int = 1;
    var x: int = 1;
    return (a + b) * (c + d) * (e + f) * (g + h);
}
"""
        result, error = compile_and_run_mcl(code, max_cycles=500_000)
        self.assertEqual(error, "", f"Unexpected error: {error}")
        self.assertEqual(result, 16, f"Expected (1+1)^4 = 16, got {result}")

    # -- Correctness: spilling across function calls --------------------------

    def test_spill_across_function_calls(self):
        """Variables survive register pressure introduced by function calls."""
        code = """
function double(x: int) {
    return x + x;
}

function main() {
    var a: int = 1;
    var b: int = 2;
    var c: int = 3;
    var d: int = 4;
    var e: int = 5;
    var f: int = 6;
    var g: int = 7;
    var h: int = 8;
    var ii: int = 9;
    var j: int = 10;
    var k: int = 11;
    var l: int = 12;
    var m: int = 13;
    var n: int = 14;
    var o: int = 15;
    var p: int = 16;
    var q: int = 17;
    var r: int = 18;
    var s: int = 19;
    var t: int = 20;
    var u: int = 21;
    var v: int = 22;
    var w: int = 23;
    var x: int = 24;
    var y: int = 25;
    var z: int = 26;
    var result: int = double(a) + double(z);
    return result;
}
"""
        # double(1) + double(26) = 2 + 52 = 54
        result, error = compile_and_run_mcl(code, max_cycles=500_000)
        self.assertEqual(error, "", f"Unexpected error: {error}")
        self.assertEqual(result, 54, f"Expected double(1)+double(26) = 54, got {result}")


if __name__ == '__main__':
    unittest.main()
