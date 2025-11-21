import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from test_mcl_comprehensive import MCLTestCase, run_mcl_test

class TestAdvancedScenarios(unittest.TestCase):
    def test_nested_loops_and_scope(self):
        code = '''
        function main() {
            var sum: int = 0;
            for (var i: int = 0; i < 3; i = i + 1) {
                for (var j: int = 0; j < 2; j = j + 1) {
                    sum = sum + i * 10 + j;
                }
            }
            return sum; // (0*10+0)+(0*10+1)+(1*10+0)+(1*10+1)+(2*10+0)+(2*10+1) = 0+1+10+11+20+21 = 63
        }
        '''
        test = MCLTestCase("nested_loops_and_scope", code, 63)
        result = run_mcl_test(test)
        self.assertEqual(result["return_value"], 63)

    def test_function_call_with_local_shadowing(self):
        code = '''
        function add(a: int, b: int) {
            var a: int = a + 1; // shadow parameter
            return a + b;
        }
        function main() {
            return add(2, 3); // (2+1)+3 = 6
        }
        '''
        test = MCLTestCase("function_call_with_local_shadowing", code, 6)
        result = run_mcl_test(test)
        self.assertEqual(result["return_value"], 6)

    def test_recursive_function_with_inner_variable(self):
        code = '''
        function sum_to(n: int) {
            if (n <= 0) return 0;
            var temp: int = sum_to(n - 1);
            return n + temp;
        }
        function main() {
            return sum_to(5); // 5+4+3+2+1 = 15
        }
        '''
        test = MCLTestCase("recursive_function_with_inner_variable", code, 15)
        result = run_mcl_test(test)
        self.assertEqual(result["return_value"], 15)

    def test_variable_lifetime_in_nested_blocks(self):
        code = '''
        function main() {
            var x: int = 1;
            if (1) {
                var x: int = 2;
                if (1) {
                    var x: int = 3;
                    if (x != 3) return 0;
                }
                if (x != 2) return 0;
            }
            if (x != 1) return 0;
            return 42;
        }
        '''
        test = MCLTestCase("variable_lifetime_in_nested_blocks", code, 42)
        result = run_mcl_test(test)
        self.assertEqual(result["return_value"], 42)

    def test_loop_variable_scope(self):
        code = '''
        function main() {
            var sum: int = 0;
            for (var i: int = 0; i < 4; i = i + 1) {
                sum = sum + i;
            }
            // i should not be visible here
            return sum; // 0+1+2+3 = 6
        }
        '''
        test = MCLTestCase("loop_variable_scope", code, 6)
        result = run_mcl_test(test)
        self.assertEqual(result["return_value"], 6)

if __name__ == "__main__":
    unittest.main(verbosity=2)
