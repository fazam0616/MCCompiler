def run_mcl(code: str) -> int:
    from tests.test_mcl_comprehensive import compile_and_run_mcl
    result, error = compile_and_run_mcl(code)
    assert error == '', f"VM/Compiler error: {error}"
    return result

def test_array_basic_assignment():
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
    assert run_mcl(code) == 30

def test_array_indexing_expression():
    code = '''
function main() {
    var arr: int[3];
    var i: int = 1;
    arr[i] = 99;
    return arr[1];
}
'''
    assert run_mcl(code) == 99

def test_pointer_basic():
    code = '''
function main() {
    var x: int = 5;
    var p: int* = @x;
    *p = 42;
    return x;
}
'''
    assert run_mcl(code) == 42

def test_pointer_to_array():
    code = '''
function main() {
    var arr: int[2];
    var p: int* = @arr[0];
    *p = 7;
    *(p + 1) = 8;
    return arr[1];
}
'''
    assert run_mcl(code) == 8

def test_array_as_parameter():
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
    assert run_mcl(code) == 123

def test_pointer_as_parameter():
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
    assert run_mcl(code) == 77

def test_pointer_arithmetic():
    code = '''
function main() {
    var arr: int[3];
    var p: int* = @arr[0];
    *(p + 2) = 55;
    return arr[2];
}
'''
    assert run_mcl(code) == 55

def test_array_deref_and_pointer_mix():
    code = '''
function main() {
    var arr: int[2];
    var p: int* = @arr[0];
    *(p + 1) = 99;
    return arr[1];
}
'''
    assert run_mcl(code) == 99
