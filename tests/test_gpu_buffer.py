import pytest
from tests.test_mcl_comprehensive import compile_and_run_mcl

def run_mcl(code: str) -> int:
    result, error = compile_and_run_mcl(code)
    assert error == '', f"VM/Compiler error: {error}"
    return result

def test_set_edit_buffer():
    code = '''
    function main() {
        setGPUBuffer(0, 1); // Set edit buffer to 1
        var val: int = getGPUBuffer(0);
        return val;
    }
    '''
    assert run_mcl(code) == 1

def test_set_display_buffer():
    code = '''
    function main() {
        setGPUBuffer(1, 1); // Set display buffer to 1
        var val: int = getGPUBuffer(1);
        return val;
    }
    '''
    assert run_mcl(code) == 1

def test_edit_buffer_reset():
    code = '''
    function main() {
        setGPUBuffer(0, 0); // Set edit buffer to 0
        var val: int = getGPUBuffer(0);
        return val;
    }
    '''
    assert run_mcl(code) == 0

def test_display_buffer_reset():
    code = '''
    function main() {
        setGPUBuffer(1, 0); // Set display buffer to 0
        var val: int = getGPUBuffer(1);
        return val;
    }
    '''
    assert run_mcl(code) == 0
