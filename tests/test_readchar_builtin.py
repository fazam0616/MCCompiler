import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.compiler.lexer import Lexer
from src.compiler.parser import Parser
from src.compiler.assembly_generator import generate_assembly
from src.vm.virtual_machine import create_vm
from src.vm.cpu import CPUState


class TestReadCharBuiltin(unittest.TestCase):
    def test_readchar_returns_input(self):
        # MCL program that calls readChar()
        mcl_src = 'function main() { var c: int = readChar(); return c; }'
        lex = Lexer(mcl_src)
        toks = lex.tokenize()
        parser = Parser(toks)
        prog = parser.parse()
        asm = generate_assembly(prog)

        # Create VM, load assembly, inject input char, run
        vm = create_vm({'enable_gpu': False})
        vm.reset()
        vm.load_program_string(asm)
        vm.cpu.set_labels(vm.memory.labels)

        # Inject a character code (ASCII 'A' = 65)
        vm.cpu.add_input_char(65)

        # Run until HALT
        vm.cpu.state = CPUState.RUNNING
        while vm.cpu.state == CPUState.RUNNING:
            if not vm.cpu.step():
                break

        # After execution, return value should be in R0
        r0 = vm.cpu.get_register(0)
        self.assertEqual(r0, 65)

        vm.shutdown()


if __name__ == '__main__':
    unittest.main()
