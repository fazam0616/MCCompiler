"""MCL Preprocessor

Handles preprocessor directives before lexing:

    #include "path/to/file.mcl"   -- splice file contents in-place
    #define NAME                   -- define a flag (no value)
    #define NAME value             -- define a macro substitution
    #undef  NAME                   -- remove a define
    #ifdef  NAME                   -- emit block if NAME is defined
    #ifndef NAME                   -- emit block if NAME is NOT defined
    #else                          -- flip the current conditional block
    #endif                         -- close a conditional block

Key design decisions:
  - Every directive line is replaced by a blank line so that lexer-reported
    line numbers stay accurate after preprocessing.
  - #define values are substituted as plain text (whole-word only, not
    re-expanded), avoiding recursive-macro complexity.
  - defines dict is shared across recursive calls so a #define inside an
    included file is visible to the includer after that point.
  - Structural directives (#ifdef/#ifndef/#else/#endif) are parsed even
    inside suppressed blocks to maintain correct nesting depth.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class PreprocessorError(Exception):
    """Raised for any preprocessor-level error."""
    def __init__(self, message: str, path: Optional[Path] = None, line: int = 0):
        loc = f"{path}:{line}: " if path else (f"line {line}: " if line else "")
        super().__init__(f"Preprocessor error: {loc}{message}")
        self.path = path
        self.line = line


# ---------------------------------------------------------------------------
# Directive pattern
# ---------------------------------------------------------------------------

# Matches lines of the form:   #directive  remainder
# Leading whitespace before '#' is allowed.
_DIRECTIVE_RE = re.compile(r'^\s*#\s*(\w+)(.*)', re.DOTALL)


def _parse_directive(line: str) -> Optional[Tuple[str, str]]:
    """Return (directive_name, remainder_text) or None if not a directive."""
    m = _DIRECTIVE_RE.match(line)
    if m:
        return m.group(1).lower(), m.group(2).strip()
    return None


def _substitute(line: str, defines: Dict[str, Optional[str]]) -> str:
    """Apply whole-word macro substitution for all defines that have a value."""
    for name, value in defines.items():
        if value is None:
            continue  # flag-only define, nothing to substitute
        # Use word-boundary replacement so SIZE doesn't replace MAXSIZE etc.
        line = re.sub(r'\b' + re.escape(name) + r'\b', value, line)
    return line


# ---------------------------------------------------------------------------
# Core preprocessor
# ---------------------------------------------------------------------------

def preprocess(
    source: str,
    base_dir: Path,
    defines: Optional[Dict[str, Optional[str]]] = None,
    _include_stack: Optional[List[Path]] = None,
) -> str:
    """Preprocess *source* text and return the expanded source string.

    Args:
        source:         Raw MCL source text.
        base_dir:       Directory used to resolve relative #include paths.
        defines:        Shared macro definition dict (mutated in-place so
                        #define in included files affects the includer).
        _include_stack: Tracks currently open files for cycle detection.
                        Pass None at the top-level call.

    Returns:
        Expanded source text ready to pass to ``tokenize()``.

    Raises:
        PreprocessorError: For missing includes, cycles, bad directives, or
                           unterminated #ifdef / #ifndef blocks.
    """
    if defines is None:
        defines = {}
    if _include_stack is None:
        _include_stack = []

    # condition_stack: list of booleans.
    #   True  → current block is active (emit lines)
    #   False → current block is suppressed
    # Start with one True so the root level is always active.
    condition_stack: List[bool] = [True]

    def active() -> bool:
        return all(condition_stack)

    output_lines: List[str] = []
    current_path: Optional[Path] = _include_stack[-1] if _include_stack else None

    for lineno, raw_line in enumerate(source.splitlines(keepends=True), start=1):
        # Strip trailing newline for directive parsing, re-add later.
        stripped = raw_line.rstrip('\n').rstrip('\r')

        parsed = _parse_directive(stripped)
        if parsed is None:
            # Ordinary source line
            if active():
                output_lines.append(_substitute(raw_line, defines))
            else:
                output_lines.append('\n')
            continue

        directive, rest = parsed
        # Always emit a blank line in place of the directive (preserves line count)
        output_lines.append('\n')

        # ------------------------------------------------------------------
        # Structural directives — parsed at ALL nesting levels (even suppressed)
        # ------------------------------------------------------------------
        if directive == 'ifdef':
            name = rest.split()[0] if rest.split() else ''
            if not name:
                raise PreprocessorError("'#ifdef' requires a name", current_path, lineno)
            # Push: True only if outer context is active AND name is defined
            condition_stack.append(active() and name in defines)
            continue

        if directive == 'ifndef':
            name = rest.split()[0] if rest.split() else ''
            if not name:
                raise PreprocessorError("'#ifndef' requires a name", current_path, lineno)
            condition_stack.append(active() and name not in defines)
            continue

        if directive == 'else':
            if len(condition_stack) < 2:
                raise PreprocessorError("'#else' without matching '#ifdef'/'#ifndef'",
                                        current_path, lineno)
            # Flip the innermost condition, but only when the outer context is active.
            # If the outer context is suppressed, both branches should be suppressed.
            outer_active = all(condition_stack[:-1])
            condition_stack[-1] = outer_active and not condition_stack[-1]
            continue

        if directive == 'endif':
            if len(condition_stack) < 2:
                raise PreprocessorError("'#endif' without matching '#ifdef'/'#ifndef'",
                                        current_path, lineno)
            condition_stack.pop()
            continue

        # ------------------------------------------------------------------
        # Content directives — only executed when the block is active
        # ------------------------------------------------------------------
        if not active():
            continue

        if directive == 'include':
            # Expect: "path/to/file.mcl"  (with quotes)
            m = re.match(r'^"([^"]+)"', rest)
            if not m:
                raise PreprocessorError(
                    f"'#include' expects a quoted path, got: {rest!r}",
                    current_path, lineno
                )
            include_rel_path = m.group(1)
            include_path = (base_dir / include_rel_path).resolve()

            if not include_path.exists():
                raise PreprocessorError(
                    f"included file not found: {include_path}",
                    current_path, lineno
                )

            if include_path in _include_stack:
                cycle = ' -> '.join(str(p) for p in _include_stack)
                raise PreprocessorError(
                    f"circular #include detected: {cycle} -> {include_path}",
                    current_path, lineno
                )

            include_text = include_path.read_text(encoding='utf-8')
            expanded = preprocess(
                include_text,
                include_path.parent,
                defines=defines,  # shared dict — mutations visible to caller
                _include_stack=_include_stack + [include_path],
            )
            # Replace our placeholder blank line with the expanded content.
            output_lines.pop()
            # Ensure the included content ends with a newline before continuing
            if expanded and not expanded.endswith('\n'):
                expanded += '\n'
            output_lines.append(expanded)
            continue

        if directive == 'define':
            parts = rest.split(None, 1)  # split on first whitespace only
            if not parts:
                raise PreprocessorError("'#define' requires at least a name",
                                        current_path, lineno)
            name = parts[0]
            if not re.fullmatch(r'[A-Za-z_]\w*', name):
                raise PreprocessorError(
                    f"'#define' name must be a valid identifier, got: {name!r}",
                    current_path, lineno
                )
            value: Optional[str] = parts[1] if len(parts) > 1 else None
            defines[name] = value
            continue

        if directive == 'undef':
            parts = rest.split()
            if not parts:
                raise PreprocessorError("'#undef' requires a name", current_path, lineno)
            defines.pop(parts[0], None)
            continue

        # Unknown directive
        raise PreprocessorError(f"unknown preprocessor directive: '#{directive}'",
                                 current_path, lineno)

    # Validate that all conditional blocks were closed
    if len(condition_stack) != 1:
        depth = len(condition_stack) - 1
        raise PreprocessorError(
            f"{depth} unterminated #ifdef/#ifndef block(s) at end of file",
            current_path
        )

    return ''.join(output_lines)
