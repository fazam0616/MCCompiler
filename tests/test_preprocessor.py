"""Tests for the MCL preprocessor.

Covers:
  - #define (flag and value forms)
  - #undef
  - #ifdef / #ifndef / #else / #endif (including nesting)
  - Macro substitution in source lines
  - #include (text splice, relative paths, shared defines)
  - Error cases: circular include, missing file, unterminated block,
    mismatched #else/#endif, bad define name, unknown directive
"""

import unittest
import sys
import os
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.compiler.preprocessor import preprocess, PreprocessorError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pp(source: str, base_dir: Path = None, defines: dict = None) -> str:
    """Convenience wrapper — strip leading indentation from multi-line strings."""
    source = textwrap.dedent(source)
    if base_dir is None:
        base_dir = Path(tempfile.gettempdir())
    kwargs = {}
    if defines is not None:
        kwargs['defines'] = defines
    return preprocess(source, base_dir, **kwargs)


# ---------------------------------------------------------------------------
# #define (flag form)
# ---------------------------------------------------------------------------

class TestDefineFlag(unittest.TestCase):

    def test_define_flag_creates_entry(self):
        defines = {}
        pp("#define MY_FLAG\n", defines=defines)
        self.assertIn('MY_FLAG', defines)
        self.assertIsNone(defines['MY_FLAG'])

    def test_define_flag_no_substitution(self):
        """A flag-only define should NOT substitute the name in source."""
        result = pp("""\
            #define FOO
            int x = FOO;
        """)
        # FOO should remain un-substituted (no value to replace with)
        self.assertIn('int x = FOO;', result)

    def test_define_multiple_flags(self):
        defines = {}
        pp("#define A\n#define B\n#define C\n", defines=defines)
        self.assertIn('A', defines)
        self.assertIn('B', defines)
        self.assertIn('C', defines)


# ---------------------------------------------------------------------------
# #define (value form) + macro substitution
# ---------------------------------------------------------------------------

class TestDefineValue(unittest.TestCase):

    def test_simple_substitution(self):
        result = pp("""\
            #define SIZE 10
            var arr: int[SIZE];
        """)
        self.assertIn('var arr: int[10];', result)
        self.assertNotIn('SIZE', result.replace('#define SIZE 10', ''))

    def test_substitution_multiple_occurrences(self):
        result = pp("""\
            #define N 5
            int a = N + N;
        """)
        self.assertIn('int a = 5 + 5;', result)

    def test_whole_word_only(self):
        """MAXSIZE should NOT be substituted when only SIZE is defined."""
        result = pp("""\
            #define SIZE 10
            int MAXSIZE = SIZE;
        """)
        self.assertIn('int MAXSIZE = 10;', result)
        self.assertIn('MAXSIZE', result)   # MAXSIZE untouched

    def test_define_string_value(self):
        result = pp("""\
            #define MSG hello
            return MSG;
        """)
        self.assertIn('return hello;', result)

    def test_define_numeric_expression(self):
        result = pp("""\
            #define LIMIT 64
            if (x < LIMIT) {
        """)
        self.assertIn('if (x < 64) {', result)

    def test_define_overwrites_previous(self):
        result = pp("""\
            #define VAL 1
            #define VAL 2
            int x = VAL;
        """)
        self.assertIn('int x = 2;', result)

    def test_define_preserves_value_with_spaces(self):
        """Value with trailing spaces in #define line."""
        defines = {}
        pp("#define ANSWER 42   \n", defines=defines)
        self.assertEqual(defines['ANSWER'], '42')


# ---------------------------------------------------------------------------
# #undef
# ---------------------------------------------------------------------------

class TestUndef(unittest.TestCase):

    def test_undef_removes_define(self):
        defines = {}
        pp("#define X 1\n#undef X\n", defines=defines)
        self.assertNotIn('X', defines)

    def test_undef_nonexistent_is_silent(self):
        """#undef of a name that was never defined should not raise."""
        pp("#undef NEVER_DEFINED\n")  # no exception

    def test_substitution_stops_after_undef(self):
        result = pp("""\
            #define VAL 99
            int a = VAL;
            #undef VAL
            int b = VAL;
        """)
        self.assertIn('int a = 99;', result)
        self.assertIn('int b = VAL;', result)   # no substitution after undef


# ---------------------------------------------------------------------------
# Conditional compilation
# ---------------------------------------------------------------------------

class TestIfdef(unittest.TestCase):

    def test_ifdef_true(self):
        result = pp("""\
            #define DEBUG
            #ifdef DEBUG
            int x = 1;
            #endif
        """)
        self.assertIn('int x = 1;', result)

    def test_ifdef_false(self):
        result = pp("""\
            #ifdef DEBUG
            int x = 1;
            #endif
        """)
        self.assertNotIn('int x = 1;', result)

    def test_ifndef_true(self):
        result = pp("""\
            #ifndef RELEASE
            int debug_mode = 1;
            #endif
        """)
        self.assertIn('int debug_mode = 1;', result)

    def test_ifndef_false(self):
        result = pp("""\
            #define RELEASE
            #ifndef RELEASE
            int debug_mode = 1;
            #endif
        """)
        self.assertNotIn('int debug_mode = 1;', result)

    def test_ifdef_else_true_branch(self):
        result = pp("""\
            #define FAST
            #ifdef FAST
            int speed = 100;
            #else
            int speed = 10;
            #endif
        """)
        self.assertIn('int speed = 100;', result)
        self.assertNotIn('int speed = 10;', result)

    def test_ifdef_else_false_branch(self):
        result = pp("""\
            #ifdef FAST
            int speed = 100;
            #else
            int speed = 10;
            #endif
        """)
        self.assertNotIn('int speed = 100;', result)
        self.assertIn('int speed = 10;', result)

    def test_ifndef_else(self):
        result = pp("""\
            #define RELEASE
            #ifndef RELEASE
            int a = 1;
            #else
            int a = 2;
            #endif
        """)
        self.assertNotIn('int a = 1;', result)
        self.assertIn('int a = 2;', result)


class TestNestedConditionals(unittest.TestCase):

    def test_nested_ifdef_both_defined(self):
        result = pp("""\
            #define A
            #define B
            #ifdef A
            #ifdef B
            int x = 1;
            #endif
            #endif
        """)
        self.assertIn('int x = 1;', result)

    def test_nested_ifdef_outer_false(self):
        result = pp("""\
            #ifdef A
            #define B
            #ifdef B
            int x = 1;
            #endif
            #endif
        """)
        self.assertNotIn('int x = 1;', result)

    def test_nested_ifdef_inner_false(self):
        result = pp("""\
            #define A
            #ifdef A
            #ifdef B
            int x = 1;
            #endif
            int y = 2;
            #endif
        """)
        self.assertNotIn('int x = 1;', result)
        self.assertIn('int y = 2;', result)

    def test_nested_else(self):
        result = pp("""\
            #define OUTER
            #ifdef OUTER
            #ifdef INNER
            int branch = 1;
            #else
            int branch = 2;
            #endif
            #endif
        """)
        self.assertNotIn('int branch = 1;', result)
        self.assertIn('int branch = 2;', result)

    def test_define_inside_suppressed_block_not_applied(self):
        """A #define inside a suppressed #ifdef block must NOT take effect."""
        result = pp("""\
            #ifdef UNDEF_FLAG
            #define SIZE 999
            #endif
            int x = SIZE;
        """)
        # SIZE should NOT be substituted because the #define was suppressed
        self.assertIn('int x = SIZE;', result)

    def test_triple_nesting(self):
        result = pp("""\
            #define L1
            #define L2
            #define L3
            #ifdef L1
            #ifdef L2
            #ifdef L3
            int deep = 1;
            #endif
            #endif
            #endif
        """)
        self.assertIn('int deep = 1;', result)


# ---------------------------------------------------------------------------
# Line number preservation
# ---------------------------------------------------------------------------

class TestLinePreservation(unittest.TestCase):

    def test_directive_replaced_by_blank_line(self):
        """Every directive line must produce exactly one blank line."""
        source = "#define X 1\nint a = X;\n"
        result = preprocess(source, Path(tempfile.gettempdir()))
        lines = result.splitlines()
        # Line 1 was a directive → blank; line 2 has the substitution
        self.assertEqual(lines[0].strip(), '')
        self.assertIn('int a = 1;', lines[1])

    def test_total_line_count_unchanged(self):
        source = "#define A\n#define B 2\nint x = B;\n"
        result = preprocess(source, Path(tempfile.gettempdir()))
        self.assertEqual(result.count('\n'), source.count('\n'))


# ---------------------------------------------------------------------------
# #include
# ---------------------------------------------------------------------------

class TestInclude(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _write(self, name: str, content: str) -> Path:
        p = self.tmp / name
        p.write_text(textwrap.dedent(content), encoding='utf-8')
        return p

    def test_basic_include(self):
        self._write('lib.mcl', """\
            function helper() {
                return 1;
            }
        """)
        result = preprocess(
            '#include "lib.mcl"\nfunction main() { return 0; }\n',
            self.tmp
        )
        self.assertIn('function helper()', result)
        self.assertIn('function main()', result)

    def test_include_preserves_surrounding_code(self):
        self._write('defs.mcl', "#define VALUE 42\n")
        result = preprocess(
            'int before = 0;\n#include "defs.mcl"\nint after = VALUE;\n',
            self.tmp
        )
        self.assertIn('int before = 0;', result)
        self.assertIn('int after = 42;', result)

    def test_include_shares_defines(self):
        """#define inside an included file must be visible after the include."""
        self._write('consts.mcl', "#define LIMIT 100\n")
        result = preprocess(
            '#include "consts.mcl"\nint x = LIMIT;\n',
            self.tmp
        )
        self.assertIn('int x = 100;', result)

    def test_define_before_include_visible_inside(self):
        """A define in the main file must be visible inside the included file."""
        self._write('check.mcl', "int val = OUTER;\n")
        result = preprocess(
            '#define OUTER 7\n#include "check.mcl"\n',
            self.tmp
        )
        self.assertIn('int val = 7;', result)

    def test_include_subdirectory(self):
        sub = self.tmp / 'sub'
        sub.mkdir()
        (sub / 'util.mcl').write_text("int util_val = 5;\n", encoding='utf-8')
        result = preprocess(
            '#include "sub/util.mcl"\n',
            self.tmp
        )
        self.assertIn('int util_val = 5;', result)

    def test_include_guard_idiom(self):
        """#ifndef / #define / #endif include guard prevents double inclusion."""
        self._write('guarded.mcl', textwrap.dedent("""\
            #ifndef GUARDED_H
            #define GUARDED_H
            int once = 1;
            #endif
        """))
        result = preprocess(
            '#include "guarded.mcl"\n#include "guarded.mcl"\n',
            self.tmp
        )
        # 'int once = 1;' should appear exactly once
        self.assertEqual(result.count('int once = 1;'), 1)

    def test_nested_include(self):
        """An included file can itself include another file."""
        self._write('inner.mcl', "int inner_val = 3;\n")
        self._write('outer.mcl', '#include "inner.mcl"\nint outer_val = 4;\n')
        result = preprocess('#include "outer.mcl"\n', self.tmp)
        self.assertIn('int inner_val = 3;', result)
        self.assertIn('int outer_val = 4;', result)

    def test_include_relative_to_included_file(self):
        """Nested includes resolve paths relative to the including file, not the root."""
        sub = self.tmp / 'sub'
        sub.mkdir()
        (sub / 'leaf.mcl').write_text("int leaf = 9;\n", encoding='utf-8')
        # mid.mcl lives in sub/ and includes leaf.mcl (also in sub/)
        (sub / 'mid.mcl').write_text('#include "leaf.mcl"\n', encoding='utf-8')
        result = preprocess('#include "sub/mid.mcl"\n', self.tmp)
        self.assertIn('int leaf = 9;', result)

    def test_conditional_include(self):
        """#include inside a suppressed block should not be processed."""
        self._write('secret.mcl', "int secret = 42;\n")
        result = preprocess(
            '#ifdef NEVER\n#include "secret.mcl"\n#endif\n',
            self.tmp
        )
        self.assertNotIn('int secret = 42;', result)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

class TestPreprocessorErrors(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _write(self, name: str, content: str) -> Path:
        p = self.tmp / name
        p.write_text(content, encoding='utf-8')
        return p

    def test_missing_include_file(self):
        with self.assertRaises(PreprocessorError) as ctx:
            preprocess('#include "nonexistent.mcl"\n', self.tmp)
        self.assertIn('not found', str(ctx.exception))

    def test_circular_include_direct(self):
        """A file that includes itself should raise PreprocessorError."""
        f = self._write('self.mcl', '#include "self.mcl"\n')
        with self.assertRaises(PreprocessorError) as ctx:
            preprocess('#include "self.mcl"\n', self.tmp)
        self.assertIn('circular', str(ctx.exception).lower())

    def test_circular_include_indirect(self):
        """A → B → A should raise PreprocessorError."""
        self._write('a.mcl', '#include "b.mcl"\n')
        self._write('b.mcl', '#include "a.mcl"\n')
        with self.assertRaises(PreprocessorError):
            preprocess('#include "a.mcl"\n', self.tmp)

    def test_unterminated_ifdef(self):
        with self.assertRaises(PreprocessorError) as ctx:
            preprocess('#ifdef FOO\nint x = 1;\n', Path(self.tmp))
        self.assertIn('unterminated', str(ctx.exception).lower())

    def test_endif_without_ifdef(self):
        with self.assertRaises(PreprocessorError) as ctx:
            preprocess('#endif\n', Path(self.tmp))
        self.assertIn('#endif', str(ctx.exception))

    def test_else_without_ifdef(self):
        with self.assertRaises(PreprocessorError) as ctx:
            preprocess('#else\n', Path(self.tmp))
        self.assertIn('#else', str(ctx.exception))

    def test_include_missing_quotes(self):
        with self.assertRaises(PreprocessorError) as ctx:
            preprocess('#include lib.mcl\n', Path(self.tmp))
        self.assertIn('quoted', str(ctx.exception).lower())

    def test_define_missing_name(self):
        with self.assertRaises(PreprocessorError) as ctx:
            preprocess('#define\n', Path(self.tmp))
        self.assertIn('#define', str(ctx.exception))

    def test_ifdef_missing_name(self):
        with self.assertRaises(PreprocessorError) as ctx:
            preprocess('#ifdef\n#endif\n', Path(self.tmp))
        self.assertIn('#ifdef', str(ctx.exception))

    def test_unknown_directive(self):
        with self.assertRaises(PreprocessorError) as ctx:
            preprocess('#pragma once\n', Path(self.tmp))
        self.assertIn('pragma', str(ctx.exception).lower())

    def test_define_invalid_name(self):
        with self.assertRaises(PreprocessorError) as ctx:
            preprocess('#define 123BAD value\n', Path(self.tmp))
        self.assertIn('identifier', str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# Integration: preprocess → tokenize → parse → generate
# ---------------------------------------------------------------------------

class TestPreprocessorIntegration(unittest.TestCase):
    """End-to-end test: preprocessed source can be fully compiled."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _compile(self, source: str) -> str:
        from src.compiler.lexer import tokenize
        from src.compiler.parser import parse
        from src.compiler.assembly_generator import generate_assembly
        expanded = preprocess(textwrap.dedent(source), self.tmp)
        tokens = tokenize(expanded)
        ast = parse(tokens)
        return generate_assembly(ast)

    def test_define_used_in_array_size(self):
        asm = self._compile("""\
            #define ARRAY_SIZE 5
            function main() {
                var arr: int[ARRAY_SIZE];
                return 0;
            }
        """)
        self.assertIsNotNone(asm)

    def test_define_used_in_expression(self):
        # The compiler evaluates MAX - 1 at runtime (no constant folding),
        # so we check that the substituted literal 100 appears in the assembly
        # and that a SUB instruction is emitted for the subtraction.
        asm = self._compile("""\
            #define MAX 100
            function main() {
                int x = MAX - 1;
                return x;
            }
        """)
        self.assertIn('100', asm)   # macro was substituted
        self.assertIn('SUB', asm)   # subtraction emitted at runtime

    def test_ifdef_selects_function(self):
        asm = self._compile("""\
            #define USE_FAST
            #ifdef USE_FAST
            function compute(x: int) {
                return x * 2;
            }
            #else
            function compute(x: int) {
                return x;
            }
            #endif
            function main() {
                return compute(5);
            }
        """)
        # The fast path multiplies by 2, so MULT should appear
        self.assertIn('MULT', asm)

    def test_include_function_definition(self):
        (self.tmp / 'utils.mcl').write_text(textwrap.dedent("""\
            function double(n: int) {
                return n * 2;
            }
        """), encoding='utf-8')
        asm = self._compile("""\
            #include "utils.mcl"
            function main() {
                return double(21);
            }
        """)
        self.assertIn('func_double', asm)
        self.assertIn('func_main', asm)

    def test_include_with_define_constant(self):
        (self.tmp / 'config.mcl').write_text("#define RESULT 77\n", encoding='utf-8')
        asm = self._compile("""\
            #include "config.mcl"
            function main() {
                return RESULT;
            }
        """)
        self.assertIn('77', asm)


if __name__ == '__main__':
    unittest.main()
