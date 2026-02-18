"""MCL Language Server

Implements Language Server Protocol for MCL language support in VSCode.
"""

import asyncio
import re
from typing import List, Optional, Dict, Any, Union
from pathlib import Path

from pygls.server import LanguageServer
from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_HOVER,
    TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL,
    TEXT_DOCUMENT_DIAGNOSTIC,
    CompletionItem,
    CompletionItemKind,
    CompletionList,
    CompletionParams,
    Hover,
    HoverParams,
    MarkupContent,
    MarkupKind,
    Position,
    Range,
    Diagnostic,
    DiagnosticSeverity,
    DocumentDiagnosticParams,
    FullDocumentDiagnosticReport,
    SemanticTokens,
    SemanticTokensParams,
    SemanticTokensLegend,
    SemanticTokenTypes,
    SemanticTokenModifiers,
    DidOpenTextDocumentParams,
    DidChangeTextDocumentParams,
    DidSaveTextDocumentParams,
    DidCloseTextDocumentParams,
    InitializeParams,
    InitializeResult,
    ServerCapabilities,
    TextDocumentSyncKind,
    CompletionOptions,
    HoverOptions,
    SemanticTokensOptions,
    DiagnosticOptions
)

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from src.compiler.lexer import tokenize, LexerError, TokenType
    from src.compiler.parser import parse, ParseError
    from src.compiler.assembly_generator import generate_assembly, CodeGenerationError
    from src.compiler.preprocessor import preprocess, PreprocessorError
except ImportError:
    # Fallback for different import contexts
    try:
        from ..compiler.lexer import tokenize, LexerError, TokenType
        from ..compiler.parser import parse, ParseError
        from ..compiler.assembly_generator import generate_assembly, CodeGenerationError
        from ..compiler.preprocessor import preprocess, PreprocessorError
    except ImportError:
        # Create stub implementations if compiler modules aren't available
        class LexerError(Exception):
            pass
        
        class ParseError(Exception):
            pass
        
        class CodeGenerationError(Exception):
            pass

        class PreprocessorError(Exception):
            pass
        
        class TokenType:
            pass
        
        def tokenize(text):
            return []
        
        def parse(tokens):
            return None
        
        def generate_assembly(ast):
            return ""

        def preprocess(source, base_dir):
            return source


class MCLLanguageServer(LanguageServer):
    """Language Server for MCL."""
    
    def __init__(self):
        super().__init__("mcl-language-server", "0.1.0")
        
        # Document cache
        self.documents: Dict[str, str] = {}
        
        # Semantic token types and modifiers
        self.semantic_token_types = [
            SemanticTokenTypes.Keyword,      # 0
            SemanticTokenTypes.Type,         # 1
            SemanticTokenTypes.Variable,     # 2
            SemanticTokenTypes.Function,     # 3
            SemanticTokenTypes.Number,       # 4
            SemanticTokenTypes.String,       # 5
            SemanticTokenTypes.Comment,      # 6
            SemanticTokenTypes.Operator,     # 7
            SemanticTokenTypes.Parameter,    # 8
        ]
        
        self.semantic_token_modifiers = [
            SemanticTokenModifiers.Declaration,  # 0
            SemanticTokenModifiers.Definition,   # 1
            SemanticTokenModifiers.Readonly,     # 2
        ]
        
        # MCL language keywords and constructs
        self.keywords = {
            'var', 'function', 'if', 'else', 'elif', 'while', 'for',
            'switch', 'case', 'default', 'return', 'break', 'continue'
        }
        
        self.operators = {
            '+', '-', '*', '/', '%', '=', '==', '!=', '<', '>', '<=', '>=',
            '&&', '||', '!', '&', '|', '^', '~', '<<', '>>', '->', '++', '--'
        }
        
        self.types = {'int', 'char', 'void'}
        
        # Preprocessor directives
        self.preprocessor_directives = [
            ('include',  '#include "file.mcl"',   'Splice another MCL file in-place at this point'),
            ('define',   '#define NAME [value]',   'Define a macro flag or text substitution'),
            ('undef',    '#undef NAME',             'Remove a previously defined macro'),
            ('ifdef',    '#ifdef NAME',             'Emit the following block only if NAME is defined'),
            ('ifndef',   '#ifndef NAME',            'Emit the following block only if NAME is NOT defined'),
            ('else',     '#else',                   'Flip the current conditional block'),
            ('endif',    '#endif',                  'Close an #ifdef / #ifndef block'),
        ]
        
        # Assembly instructions for completion
        self.assembly_instructions = {
            'LOAD', 'READ', 'MVR', 'MVM', 'ADD', 'SUB', 'MULT', 'DIV',
            'SHL', 'SHR', 'SHLR', 'JMP', 'JAL', 'JBT', 'JZ', 'JNZ',
            'DRLINE', 'DRGRD', 'CLRGRID', 'LDSPR', 'DRSPR', 'LDTXT', 'DRTXT', 'SCRLBFR'
        }


mcl_server = MCLLanguageServer()


@mcl_server.feature(TEXT_DOCUMENT_COMPLETION)
async def completion(params: CompletionParams) -> CompletionList:
    """Provide completion items."""
    document_uri = params.text_document.uri
    position = params.position
    
    if document_uri not in mcl_server.documents:
        return CompletionList(is_incomplete=False, items=[])
    
    text = mcl_server.documents[document_uri]
    lines = text.split('\n')
    
    if position.line >= len(lines):
        return CompletionList(is_incomplete=False, items=[])
    
    current_line = lines[position.line][:position.character]
    
    # Determine context and provide appropriate completions
    items = []
    
    # Preprocessor directives — triggered when line starts with '#'
    stripped = current_line.lstrip()
    if stripped.startswith('#'):
        for name, signature, description in mcl_server.preprocessor_directives:
            items.append(CompletionItem(
                label=f"#{name}",
                kind=CompletionItemKind.Keyword,
                detail=signature,
                documentation=description,
                insert_text=f"#{name}",
            ))
        return CompletionList(is_incomplete=False, items=items)
    
    # Keywords
    for keyword in mcl_server.keywords:
        items.append(CompletionItem(
            label=keyword,
            kind=CompletionItemKind.Keyword,
            detail=f"MCL keyword: {keyword}"
        ))
    
    # Types
    for type_name in mcl_server.types:
        items.append(CompletionItem(
            label=type_name,
            kind=CompletionItemKind.TypeParameter,
            detail=f"MCL type: {type_name}"
        ))
    
    # Built-in functions/constructs
    builtins = [
        ('main', 'function main() -> int', 'Main function'),
        ('printf', 'printf(format, ...)', 'Print formatted output (if supported)'),
    ]
    
    for name, signature, description in builtins:
        items.append(CompletionItem(
            label=name,
            kind=CompletionItemKind.Function,
            detail=signature,
            documentation=description
        ))
    
    # If in assembly context, add assembly instructions
    if '.asm' in document_uri or 'assembly' in current_line.lower():
        for instr in mcl_server.assembly_instructions:
            items.append(CompletionItem(
                label=instr,
                kind=CompletionItemKind.Function,
                detail=f"Assembly instruction: {instr}"
            ))
    
    return CompletionList(is_incomplete=False, items=items)


@mcl_server.feature(TEXT_DOCUMENT_HOVER)
async def hover(params: HoverParams) -> Optional[Hover]:
    """Provide hover information."""
    document_uri = params.text_document.uri
    position = params.position
    
    if document_uri not in mcl_server.documents:
        return None
    
    text = mcl_server.documents[document_uri]
    lines = text.split('\n')
    
    if position.line >= len(lines):
        return None
    
    line = lines[position.line]
    
    # Find word at position
    word_start = position.character
    word_end = position.character
    
    while word_start > 0 and (line[word_start - 1].isalnum() or line[word_start - 1] == '_'):
        word_start -= 1
    
    while word_end < len(line) and (line[word_end].isalnum() or line[word_end] == '_'):
        word_end += 1
    
    if word_start == word_end:
        return None
    
    word = line[word_start:word_end]
    
    # Check for preprocessor directive (word preceded by '#' on the same line)
    pre_word = line[:word_start].rstrip()
    if pre_word.endswith('#') or word.startswith('#'):
        directive = word.lstrip('#')
        directive_descriptions = {
            'include': '**#include "path"**\n\nSplice another `.mcl` file in-place. Path is relative to the current file.\n\nExample: `#include "utils/math.mcl"`',
            'define':  '**#define NAME [value]**\n\nDefine a macro flag or text-substitution macro.\n\n- Flag form: `#define DEBUG`\n- Value form: `#define SIZE 64`',
            'undef':   '**#undef NAME**\n\nRemove a previously defined macro name.',
            'ifdef':   '**#ifdef NAME**\n\nEmit the enclosed block only when `NAME` has been `#define`d.',
            'ifndef':  '**#ifndef NAME**\n\nEmit the enclosed block only when `NAME` has **not** been `#define`d. Typical use: include guards.',
            'else':    '**#else**\n\nAlternative branch for an open `#ifdef` / `#ifndef` block.',
            'endif':   '**#endif**\n\nClose an open `#ifdef` / `#ifndef` block.',
        }
        if directive in directive_descriptions:
            return Hover(
                contents=MarkupContent(
                    kind=MarkupKind.Markdown,
                    value=directive_descriptions[directive]
                ),
                range=Range(
                    start=Position(line=position.line, character=word_start),
                    end=Position(line=position.line, character=word_end)
                )
            )
    
    # Provide hover information based on word
    hover_text = None
    
    if word in mcl_server.keywords:
        hover_descriptions = {
            'var': 'Declares a new variable',
            'function': 'Declares a new function',
            'if': 'Conditional statement',
            'else': 'Alternative branch in conditional statement',
            'elif': 'Additional conditional branch',
            'while': 'Loop that continues while condition is true',
            'for': 'Loop with initialization, condition, and increment',
            'switch': 'Multi-way branch statement',
            'case': 'Branch case in switch statement',
            'default': 'Default case in switch statement',
            'return': 'Returns from function',
            'break': 'Exits from loop or switch',
            'continue': 'Skips to next iteration of loop'
        }
        hover_text = hover_descriptions.get(word, f'MCL keyword: {word}')
    
    elif word in mcl_server.types:
        type_descriptions = {
            'int': 'Integer type - 32-bit signed integer',
            'char': 'Character type - stored as ASCII value',
            'void': 'Void type - used for functions with no return value'
        }
        hover_text = type_descriptions.get(word, f'MCL type: {word}')
    
    elif word in mcl_server.assembly_instructions:
        instruction_descriptions = {
            'LOAD': 'LOAD A, B - Load data at register A into RAM address B',
            'READ': 'READ A, B - Load data at RAM address A into register B',
            'MVR': 'MVR A, B - Copy register A to register B',
            'MVM': 'MVM A, B - Copy RAM address A to RAM address B',
            'ADD': 'ADD A, B - Add A and B, store result in return registers',
            'SUB': 'SUB A, B - Subtract B from A, store result in return registers',
            'MULT': 'MULT A, B - Multiply A and B, store result in return registers',
            'DIV': 'DIV A, B - Divide A by B, store result in return registers',
            'SHL': 'SHL A, B - Shift A left by B bits',
            'SHR': 'SHR A, B - Shift A right by B bits',
            'JMP': 'JMP A - Jump to address A',
            'JAL': 'JAL A - Jump to address A and store return address',
            'JBT': 'JBT A, x, y - Jump to A if register x > register y',
            'JZ': 'JZ A, x - Jump to A if register x == 0',
            'JNZ': 'JNZ A, x - Jump to A if register x != 0'
        }
        hover_text = instruction_descriptions.get(word, f'Assembly instruction: {word}')
    
    if hover_text:
        return Hover(
            contents=MarkupContent(
                kind=MarkupKind.Markdown,
                value=f"**{word}**\n\n{hover_text}"
            ),
            range=Range(
                start=Position(line=position.line, character=word_start),
                end=Position(line=position.line, character=word_end)
            )
        )
    
    return None


@mcl_server.feature(TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL)
async def semantic_tokens(params: SemanticTokensParams) -> SemanticTokens:
    """Provide semantic tokens for syntax highlighting."""
    document_uri = params.text_document.uri
    
    if document_uri not in mcl_server.documents:
        return SemanticTokens(data=[])
    
    text = mcl_server.documents[document_uri]
    
    try:
        tokens = tokenize(text)
        semantic_data = []
        
        prev_line = 0
        prev_char = 0
        
        for token in tokens:
            if token.type == TokenType.EOF:
                continue
            
            # Calculate relative position
            delta_line = token.line - 1 - prev_line  # Convert to 0-based
            delta_char = token.column - 1 - (prev_char if delta_line == 0 else 0)
            
            # Determine token type
            token_type_idx = 0  # Default to keyword
            token_modifiers = 0
            
            if token.type in [TokenType.VAR, TokenType.IF, TokenType.ELSE, TokenType.ELIF,
                            TokenType.WHILE, TokenType.FOR, TokenType.SWITCH, TokenType.CASE,
                            TokenType.DEFAULT, TokenType.FUNCTION, TokenType.RETURN,
                            TokenType.BREAK, TokenType.CONTINUE]:
                token_type_idx = 0  # Keyword
            
            elif token.type == TokenType.IDENTIFIER:
                # Determine if it's a function, variable, etc.
                if token.value in mcl_server.types:
                    token_type_idx = 1  # Type
                else:
                    token_type_idx = 2  # Variable (default)
            
            elif token.type == TokenType.INTEGER:
                token_type_idx = 4  # Number
            
            elif token.type == TokenType.CHAR:
                token_type_idx = 5  # String (character)
            
            elif token.type == TokenType.COMMENT:
                token_type_idx = 6  # Comment
            
            elif token.type in [TokenType.PLUS, TokenType.MINUS, TokenType.MULTIPLY,
                              TokenType.DIVIDE, TokenType.MODULO, TokenType.ASSIGN,
                              TokenType.EQUALS, TokenType.NOT_EQUALS, TokenType.LESS_THAN,
                              TokenType.GREATER_THAN, TokenType.LESS_EQUAL,
                              TokenType.GREATER_EQUAL, TokenType.LOGICAL_AND,
                              TokenType.LOGICAL_OR, TokenType.LOGICAL_NOT,
                              TokenType.BITWISE_AND, TokenType.BITWISE_OR,
                              TokenType.BITWISE_XOR, TokenType.BITWISE_NOT,
                              TokenType.SHIFT_LEFT, TokenType.SHIFT_RIGHT]:
                token_type_idx = 7  # Operator
            
            # Add semantic token data
            semantic_data.extend([
                delta_line,
                delta_char,
                len(token.value),
                token_type_idx,
                token_modifiers
            ])
            
            prev_line = token.line - 1
            prev_char = token.column - 1
        
        return SemanticTokens(data=semantic_data)
    
    except Exception:
        # If tokenization fails, return empty tokens
        return SemanticTokens(data=[])


@mcl_server.feature(TEXT_DOCUMENT_DIAGNOSTIC)
async def diagnostics(params: DocumentDiagnosticParams) -> FullDocumentDiagnosticReport:
    """Provide diagnostics (errors, warnings)."""
    document_uri = params.text_document.uri
    
    if document_uri not in mcl_server.documents:
        return FullDocumentDiagnosticReport(kind="full", items=[])
    
    text = mcl_server.documents[document_uri]
    diagnostic_items = []
    
    try:
        # Run the preprocessor first (use a dummy base dir since we have no real path)
        from pathlib import Path
        import re
        # Extract a plausible base dir from the URI (file:// scheme)
        base_dir = Path('.')
        if document_uri.startswith('file://'):
            raw = document_uri[7:]
            # On Windows URIs look like file:///C:/path/to/file.mcl
            raw = raw.lstrip('/')
            try:
                base_dir = Path(raw).parent
            except Exception:
                pass
        
        try:
            expanded_text = preprocess(text, base_dir)
        except PreprocessorError as e:
            # Extract line number from error message if available
            m = re.search(r':(\d+):', str(e))
            err_line = int(m.group(1)) - 1 if m else 0
            diagnostic_items.append(Diagnostic(
                range=Range(
                    start=Position(line=err_line, character=0),
                    end=Position(line=err_line, character=200)
                ),
                message=str(e),
                severity=DiagnosticSeverity.Error,
                source="mcl-preprocessor"
            ))
            return FullDocumentDiagnosticReport(kind="full", items=diagnostic_items)
    except Exception:
        expanded_text = text  # fall back to raw text on any unexpected error
    
    try:
        # Try to tokenize and parse
        tokens = tokenize(expanded_text)
        
        try:
            ast = parse(tokens)
            
            try:
                # Try to generate assembly to catch semantic errors
                generate_assembly(ast)
            except CodeGenerationError as e:
                # Semantic error
                diagnostic_items.append(Diagnostic(
                    range=Range(
                        start=Position(line=0, character=0),
                        end=Position(line=0, character=len(text.split('\n')[0]) if text else 0)
                    ),
                    message=str(e),
                    severity=DiagnosticSeverity.Error,
                    source="mcl-compiler"
                ))
        
        except ParseError as e:
            # Parse error
            line_num = getattr(e, 'token', None)
            if line_num and hasattr(line_num, 'line'):
                line = line_num.line - 1  # Convert to 0-based
                col = line_num.column - 1
            else:
                line = 0
                col = 0
            
            diagnostic_items.append(Diagnostic(
                range=Range(
                    start=Position(line=line, character=col),
                    end=Position(line=line, character=col + 10)
                ),
                message=str(e),
                severity=DiagnosticSeverity.Error,
                source="mcl-parser"
            ))
    
    except LexerError as e:
        # Lexical error
        line = getattr(e, 'line', 1) - 1  # Convert to 0-based
        col = getattr(e, 'column', 1) - 1
        
        diagnostic_items.append(Diagnostic(
            range=Range(
                start=Position(line=line, character=col),
                end=Position(line=line, character=col + 5)
            ),
            message=str(e),
            severity=DiagnosticSeverity.Error,
            source="mcl-lexer"
        ))
    
    return FullDocumentDiagnosticReport(kind="full", items=diagnostic_items)


# Document synchronization
@mcl_server.feature("textDocument/didOpen")
async def did_open(params: DidOpenTextDocumentParams):
    """Handle document open event."""
    document_uri = params.text_document.uri
    text = params.text_document.text
    mcl_server.documents[document_uri] = text


@mcl_server.feature("textDocument/didChange")
async def did_change(params: DidChangeTextDocumentParams):
    """Handle document change event."""
    document_uri = params.text_document.uri
    
    for change in params.content_changes:
        if hasattr(change, 'text'):
            # Full document update
            mcl_server.documents[document_uri] = change.text
        elif hasattr(change, 'range'):
            # Incremental update (not implemented yet)
            pass


@mcl_server.feature("textDocument/didSave")
async def did_save(params: DidSaveTextDocumentParams):
    """Handle document save event."""
    pass  # Could trigger compilation here


@mcl_server.feature("textDocument/didClose")
async def did_close(params: DidCloseTextDocumentParams):
    """Handle document close event."""
    document_uri = params.text_document.uri
    if document_uri in mcl_server.documents:
        del mcl_server.documents[document_uri]


@mcl_server.feature("initialize")
async def initialize(params: InitializeParams) -> InitializeResult:
    """Initialize the language server."""
    return InitializeResult(
        capabilities=ServerCapabilities(
            text_document_sync=TextDocumentSyncKind.Full,
            completion_provider=CompletionOptions(trigger_characters=[".", ":"]),
            hover_provider=HoverOptions(),
            semantic_tokens_provider=SemanticTokensOptions(
                legend=SemanticTokensLegend(
                    token_types=mcl_server.semantic_token_types,
                    token_modifiers=mcl_server.semantic_token_modifiers
                ),
                full=True
            ),
            diagnostic_provider=DiagnosticOptions(
                inter_file_dependencies=False,
                workspace_diagnostics=False
            )
        )
    )


def start_server():
    """Start the MCL language server."""
    mcl_server.start_tcp("localhost", 2087)


if __name__ == "__main__":
    start_server()