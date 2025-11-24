import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.compiler.lexer import Lexer
from src.compiler.parser import Parser
from src.compiler.assembly_generator import generate_assembly
from tests.test_assembly_framework import AssemblyTestCase, run_assembly_test


class TestAsmBuiltin(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
