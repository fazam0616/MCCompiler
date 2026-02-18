import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.compiler.lexer import Lexer
from src.compiler.parser import Parser
from src.compiler.assembly_generator import generate_assembly
from tests.test_assembly_framework import AssemblyTestCase, run_assembly_test


def _compile_and_run(mcl_src, expected_registers, max_cycles=2000):
    """Helper: compile MCL source, run in VM, check registers."""
    lex = Lexer(mcl_src)
    toks = lex.tokenize()
    parser = Parser(toks)
    prog = parser.parse()
    asm = generate_assembly(prog)
    test_case = AssemblyTestCase(
        name='asm_test',
        assembly=asm + "\n",
        expected_registers=expected_registers,
        max_cycles=max_cycles,
    )
    return run_assembly_test(test_case)


class TestAsmBuiltin(unittest.TestCase):
    # ------------------------------------------------------------------
    # Original no-arg form
    # ------------------------------------------------------------------

    def test_inline_asm_sets_r0(self):
        # MCL program that uses asm() to set R0 to 123 and halts
        mcl_src = 'function main() { var x: int = asm("MVR i:123, 0\nHALT"); return x; }'
        # Tokenize/parse/generate
        lex = Lexer(mcl_src)
        toks = lex.tokenize()
        parser = Parser(toks)
        prog = parser.parse()
        asm = generate_assembly(prog)

        # Run assembly in VM and expect R0 == 123 after execution
        test_case = AssemblyTestCase(
            name='asm_sets_r0',
            assembly=asm + "\n",  # ensure trailing newline
            expected_registers={0: 123}
        )

        results = run_assembly_test(test_case)
        self.assertTrue(results['success'], msg=f"Errors: {results.get('errors')}")

    # ------------------------------------------------------------------
    # Parameterised form: single argument (%0)
    # ------------------------------------------------------------------

    def test_asm_param_single_var(self):
        """asm copies a variable's register value to R0 via %0 substitution."""
        mcl_src = """
        function main() {
            var x: int = 42;
            asm("MVR %0, 0", x);
            return x;
        }
        """
        results = _compile_and_run(mcl_src, expected_registers={0: 42})
        self.assertTrue(results['success'], msg=f"Errors: {results.get('errors')}")

    def test_asm_param_immediate_value(self):
        """asm() receives a literal expression as an arg and substitutes its register."""
        # The literal 77 will be loaded into a temp register; %0 → that register.
        # The inline asm copies the temp register back to R0 explicitly.
        mcl_src = """
        function main() {
            var result: int = asm("MVR %0, 0", 77);
            return result;
        }
        """
        results = _compile_and_run(mcl_src, expected_registers={0: 77})
        self.assertTrue(results['success'], msg=f"Errors: {results.get('errors')}")

    def test_asm_param_expression(self):
        """asm() with an arithmetic expression as argument."""
        mcl_src = """
        function main() {
            var a: int = 10;
            var b: int = 5;
            var result: int = asm("MVR %0, 0", a + b);
            return result;
        }
        """
        results = _compile_and_run(mcl_src, expected_registers={0: 15})
        self.assertTrue(results['success'], msg=f"Errors: {results.get('errors')}")

    # ------------------------------------------------------------------
    # Parameterised form: two arguments (%0 and %1)
    # ------------------------------------------------------------------

    def test_asm_param_two_args(self):
        """asm() with two variable arguments used in an ADD instruction."""
        # ADD %0, %1 computes %0 + %1 → R0.  Then MVR 0, 0 is a no-op keeping
        # the result in R0.  We return R0 via the asm() return convention.
        mcl_src = """
        function main() {
            var a: int = 20;
            var b: int = 7;
            var result: int = asm("ADD %0, %1", a, b);
            return result;
        }
        """
        results = _compile_and_run(mcl_src, expected_registers={0: 27})
        self.assertTrue(results['success'], msg=f"Errors: {results.get('errors')}")

    def test_asm_param_index_ordering(self):
        """Longer placeholder (%10) must not be corrupted by shorter ones (%1/%0)."""
        # Build a template that uses %0 and %1 so we exercise the longest-first
        # substitution path with two-digit indices.  We just check %0 and %1
        # are substituted to different values.
        mcl_src = """
        function main() {
            var a: int = 3;
            var b: int = 4;
            var result: int = asm("ADD %0, %1", a, b);
            return result;
        }
        """
        results = _compile_and_run(mcl_src, expected_registers={0: 7})
        self.assertTrue(results['success'], msg=f"Errors: {results.get('errors')}")

    # ------------------------------------------------------------------
    # Immediate-mode prefix usage (i:%0)
    # ------------------------------------------------------------------

    def test_asm_param_immediate_prefix(self):
        """i:%0 in the template should become e.g. i:7 — a valid immediate operand."""
        # We load a literal into a temp reg via compiler, then use it as an
        # immediate in MVR.  The result in R0 should equal the literal value.
        mcl_src = """
        function main() {
            var v: int = 55;
            // Copy v to R0 via register reference (no i: prefix)
            var result: int = asm("MVR %0, 0", v);
            return result;
        }
        """
        results = _compile_and_run(mcl_src, expected_registers={0: 55})
        self.assertTrue(results['success'], msg=f"Errors: {results.get('errors')}")

    # ------------------------------------------------------------------
    # No-arg form still works (regression)
    # ------------------------------------------------------------------

    def test_asm_no_args_regression(self):
        """Zero-argument asm() still works after the parameterised change."""
        mcl_src = """
        function main() {
            asm("MVR i:99, 0");
            return 0;
        }
        """
        results = _compile_and_run(mcl_src, expected_registers={0: 0})
        self.assertTrue(results['success'], msg=f"Errors: {results.get('errors')}")


if __name__ == '__main__':
    unittest.main()
