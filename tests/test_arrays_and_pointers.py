import unittest
import sys
import os

# Add tests directory to path
sys.path.insert(0, os.path.dirname(__file__))

from test_mcl_comprehensive import compile_and_run_mcl


class TestArraysAndPointers(unittest.TestCase):
    """Test array and pointer functionality in MCL."""
    
    def run_mcl(self, code: str) -> int:
        """Helper to compile and run MCL code, failing test on errors.

        The VM stores register values as unsigned 16-bit integers, so
        sign-extend anything in the upper half of the 16-bit range so
        that callers can compare against expected signed Python ints
        (e.g. -50) without conversion.
        """
        result, error = compile_and_run_mcl(code)
        if error:
            self.fail(f"VM/Compiler error: {error}")
        if result > 32767:
            result -= 65536
        return result
    
    def test_array_basic_assignment(self):
        """Test basic array assignment and indexing."""
        code = '''
function main() {
    var arr: int[4];
    arr[0] = 10;
    arr[1] = 20;
    arr[2] = 30;
    arr[3] = 40;
    return arr[2];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 30)

    def test_array_indexing_expression(self):
        """Test array indexing with variable expression."""
        code = '''
function main() {
    var arr: int[3];
    var i: int = 1;
    arr[i] = 99;
    return arr[1];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 99)

    def test_pointer_basic(self):
        """Test basic pointer operations."""
        code = '''
function main() {
    var x: int = 5;
    var p: int* = @x;
    *p = 42;
    return x;
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 42)

    def test_pointer_to_array(self):
        """Test pointer to array element with arithmetic."""
        code = '''
function main() {
    var arr: int[2];
    var p: int* = @arr[0];
    *p = 7;
    *(p + 1) = 8;
    return arr[1];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 8)

    def test_array_as_parameter(self):
        """Test passing array as function parameter."""
        code = '''
function set_first(arr: int[3]) {
    arr[0] = 123;
}
function main() {
    var arr: int[3];
    set_first(arr);
    return arr[0];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 123)

    def test_pointer_as_parameter(self):
        """Test passing pointer as function parameter."""
        code = '''
function set_value(p: int*) {
    *p = 77;
}
function main() {
    var x: int = 0;
    set_value(@x);
    return x;
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 77)

    def test_pointer_arithmetic(self):
        """Test pointer arithmetic operations."""
        code = '''
function main() {
    var arr: int[3];
    var p: int* = @arr[0];
    *(p + 2) = 55;
    return arr[2];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 55)

    def test_array_deref_and_pointer_mix(self):
        """Test mixing array indexing and pointer dereferencing."""
        code = '''
function main() {
    var arr: int[2];
    var p: int* = @arr[0];
    *(p + 1) = 99;
    return arr[1];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 99)

    # ------------------------------------------------------------------
    # Tests for array literal initializers: var arr: int[N] = { ... }
    # These previously failed because the compiler stored a pointer to a
    # temp allocation at symbol.address instead of placing the values
    # there directly, while array-access code used symbol.address as the
    # direct element base.
    # ------------------------------------------------------------------

    def test_local_array_literal_init_middle_element(self):
        """var arr: int[3] = {10, 20, 30} — reading a non-zero index."""
        code = '''
function main() {
    var arr: int[3] = {10, 20, 30};
    return arr[1];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 20)

    def test_local_array_literal_init_first_element(self):
        """var arr: int[3] = {10, 20, 30} — reading element [0]."""
        code = '''
function main() {
    var arr: int[3] = {10, 20, 30};
    return arr[0];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 10)

    def test_local_array_literal_init_last_element(self):
        """var arr: int[3] = {10, 20, 30} — reading last element."""
        code = '''
function main() {
    var arr: int[3] = {10, 20, 30};
    return arr[2];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 30)

    def test_local_array_literal_init_negative_values(self):
        """Literal init with negative values (as used in 3d_cube vertices)."""
        code = '''
function main() {
    var arr: int[3] = {-50, -50, -50};
    return arr[0];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, -50)

    def test_local_array_literal_init_mixed_signs(self):
        """Literal init with mixed positive and negative values."""
        code = '''
function main() {
    var arr: int[6] = {-50, -50, -50, 50, -50, -50};
    return arr[3];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 50)

    def test_local_array_literal_init_sum_all(self):
        """Sum all elements of a literal-initialised array."""
        code = '''
function main() {
    var arr: int[4] = {1, 2, 3, 4};
    return arr[0] + arr[1] + arr[2] + arr[3];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 10)

    def test_local_array_literal_init_modify_element(self):
        """Init with literal then overwrite one element."""
        code = '''
function main() {
    var arr: int[3] = {10, 20, 30};
    arr[1] = 99;
    return arr[1];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 99)

    def test_local_array_literal_init_unmodified_elements_survive(self):
        """Overwriting one element must not corrupt neighbours."""
        code = '''
function main() {
    var arr: int[3] = {10, 20, 30};
    arr[1] = 99;
    return arr[0] + arr[2];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 40)

    def test_local_array_literal_init_variable_index(self):
        """Access literal-initialised array via a variable index."""
        code = '''
function main() {
    var arr: int[4] = {5, 10, 15, 20};
    var i: int = 2;
    return arr[i];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 15)

    def test_local_array_literal_init_large(self):
        """24-element literal init (cube vertex case) — check corner elements."""
        code = '''
function main() {
    var v: int[24] = {
        -50, -50, -50,
         50, -50, -50,
         50,  50, -50,
        -50,  50, -50,
        -50, -50,  50,
         50, -50,  50,
         50,  50,  50,
        -50,  50,  50
    };
    return v[0] + v[6] + v[21];
}
'''
        result = self.run_mcl(code)
        # v[0]=-50, v[6]=50, v[21]=-50  →  -50
        self.assertEqual(result, -50)

    def test_global_array_literal_init(self):
        """Global array with literal initializer."""
        code = '''
var g: int[3] = {100, 200, 300};
function main() {
    return g[1];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 200)

    def test_two_literal_arrays_independent(self):
        """Two literal-initialised arrays must not share storage."""
        code = '''
function main() {
    var a: int[3] = {1, 2, 3};
    var b: int[3] = {4, 5, 6};
    return a[2] + b[0];
}
'''
        result = self.run_mcl(code)
        self.assertEqual(result, 7)


if __name__ == '__main__':
    unittest.main()
