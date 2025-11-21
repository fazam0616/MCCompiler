"""MCL Lexical Analyzer

Tokenizes MCL source code into a stream of tokens for parsing.
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Optional, Iterator
import re


class TokenType(Enum):
    # Literals
    INTEGER = auto()
    CHAR = auto()
    IDENTIFIER = auto()
    
    # Keywords
    VAR = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    SWITCH = auto()
    CASE = auto()
    DEFAULT = auto()
    FUNCTION = auto()
    RETURN = auto()
    BREAK = auto()
    CONTINUE = auto()
    AND = auto()
    OR = auto()
    XOR = auto()
    NOT = auto()
    
    # GPU built-in functions
    DRAWLINE = auto()
    FILLGRID = auto()
    CLEARGRID = auto()
    LOADSPRITE = auto()
    DRAWSPRITE = auto()
    LOADTEXT = auto()
    DRAWTEXT = auto()
    SCROLLBUFFER = auto()
    SETGPUBUFFER = auto()
    GETGPUBUFFER = auto()
    
    # Memory management functions
    MALLOC = auto()
    FREE = auto()
    
    # Operators
    PLUS = auto()
    MINUS = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    MODULO = auto()
    ASSIGN = auto()
    EQUALS = auto()
    NOT_EQUALS = auto()
    LESS_THAN = auto()
    GREATER_THAN = auto()
    LESS_EQUAL = auto()
    GREATER_EQUAL = auto()
    LOGICAL_AND = auto()
    LOGICAL_OR = auto()
    LOGICAL_NOT = auto()
    BITWISE_AND = auto()
    BITWISE_OR = auto()
    BITWISE_XOR = auto()
    BITWISE_NOT = auto()
    SHIFT_LEFT = auto()
    SHIFT_RIGHT = auto()
    
    # Delimiters
    SEMICOLON = auto()
    COMMA = auto()
    COLON = auto()  # :
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    LEFT_BRACKET = auto()
    RIGHT_BRACKET = auto()
    AT = auto()  # @ (address-of)
    ASTERISK = auto()  # * (dereference)
    
    # Special
    NEWLINE = auto()
    EOF = auto()
    COMMENT = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int
    
    def __str__(self) -> str:
        return f"Token({self.type.name}, '{self.value}', {self.line}:{self.column})"


class LexerError(Exception):
    """Exception raised for lexical analysis errors."""
    def __init__(self, message: str, line: int, column: int):
        super().__init__(f"Lexer error at {line}:{column}: {message}")
        self.line = line
        self.column = column


class Lexer:
    """MCL Lexical Analyzer"""
    
    KEYWORDS = {
        'var': TokenType.VAR,
        'if': TokenType.IF,
        'else': TokenType.ELSE,
        'while': TokenType.WHILE,
        'for': TokenType.FOR,
        'switch': TokenType.SWITCH,
        'case': TokenType.CASE,
        'default': TokenType.DEFAULT,
        'function': TokenType.FUNCTION,
        'return': TokenType.RETURN,
        'break': TokenType.BREAK,
        'continue': TokenType.CONTINUE,
        'and': TokenType.AND,
        'or': TokenType.OR,
        'xor': TokenType.XOR,
        'not': TokenType.NOT,
        
        # GPU built-in functions
        'drawLine': TokenType.DRAWLINE,
        'fillGrid': TokenType.FILLGRID,
        'clearGrid': TokenType.CLEARGRID,
        'loadSprite': TokenType.LOADSPRITE,
        'drawSprite': TokenType.DRAWSPRITE,
        'loadText': TokenType.LOADTEXT,
        'drawText': TokenType.DRAWTEXT,
        'scrollBuffer': TokenType.SCROLLBUFFER,
        'setGPUBuffer': TokenType.SETGPUBUFFER,
        'getGPUBuffer': TokenType.GETGPUBUFFER,
        
        # Memory management functions
        'malloc': TokenType.MALLOC,
        'free': TokenType.FREE,
    }
    
    OPERATORS = {
        '+': TokenType.PLUS,
        '-': TokenType.MINUS,
        '/': TokenType.DIVIDE,
        '%': TokenType.MODULO,
        '=': TokenType.ASSIGN,
        '==': TokenType.EQUALS,
        '!=': TokenType.NOT_EQUALS,
        '<': TokenType.LESS_THAN,
        '>': TokenType.GREATER_THAN,
        '<=': TokenType.LESS_EQUAL,
        '>=': TokenType.GREATER_EQUAL,
        '&&': TokenType.LOGICAL_AND,
        '||': TokenType.LOGICAL_OR,
        '!': TokenType.LOGICAL_NOT,
        '&': TokenType.BITWISE_AND,
        '|': TokenType.BITWISE_OR,
        '^': TokenType.BITWISE_XOR,
        '~': TokenType.BITWISE_NOT,
        '<<': TokenType.SHIFT_LEFT,
        '>>': TokenType.SHIFT_RIGHT,
        '@': TokenType.AT,
    }
    
    DELIMITERS = {
        ';': TokenType.SEMICOLON,
        ',': TokenType.COMMA,
        ':': TokenType.COLON,
        '(': TokenType.LEFT_PAREN,
        ')': TokenType.RIGHT_PAREN,
        '{': TokenType.LEFT_BRACE,
        '}': TokenType.RIGHT_BRACE,
        '[': TokenType.LEFT_BRACKET,
        ']': TokenType.RIGHT_BRACKET,
    }
    
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
    
    def error(self, message: str) -> None:
        """Raise a lexer error at the current position."""
        raise LexerError(message, self.line, self.column)
    
    def peek(self, offset: int = 0) -> Optional[str]:
        """Look ahead at character without consuming it."""
        pos = self.pos + offset
        if pos >= len(self.text):
            return None
        return self.text[pos]
    
    def advance(self) -> Optional[str]:
        """Consume and return the current character."""
        if self.pos >= len(self.text):
            return None
        
        char = self.text[self.pos]
        self.pos += 1
        
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        
        return char
    
    def skip_whitespace(self) -> None:
        """Skip whitespace characters except newlines."""
        while self.peek() and self.peek() in ' \t\r':
            self.advance()
    
    def read_number(self) -> Token:
        """Read an integer literal (decimal or hexadecimal)."""
        start_pos = (self.line, self.column)
        value = ""
        
        # Check for hexadecimal prefix
        if self.peek() == '0' and self.peek(1) and self.peek(1).lower() == 'x':
            self.advance()  # consume '0'
            self.advance()  # consume 'x'
            value = "0x"
            
            if not self.peek() or not self.peek().lower() in '0123456789abcdef':
                self.error("Invalid hexadecimal number")
            
            while self.peek() and self.peek().lower() in '0123456789abcdef':
                value += self.advance()
        else:
            # Decimal number
            while self.peek() and self.peek().isdigit():
                value += self.advance()
        
        return Token(TokenType.INTEGER, value, start_pos[0], start_pos[1])
    
    def read_identifier(self) -> Token:
        """Read an identifier or keyword."""
        start_pos = (self.line, self.column)
        value = ""
        
        while (self.peek() and 
               (self.peek().isalnum() or self.peek() == '_')):
            value += self.advance()
        
        token_type = self.KEYWORDS.get(value, TokenType.IDENTIFIER)
        return Token(token_type, value, start_pos[0], start_pos[1])
    
    def read_char_literal(self) -> Token:
        """Read a character literal."""
        start_pos = (self.line, self.column)
        self.advance()  # consume opening quote
        
        if not self.peek():
            self.error("Unterminated character literal")
        
        value = ""
        if self.peek() == '\\':
            # Escape sequence
            self.advance()  # consume backslash
            if not self.peek():
                self.error("Unterminated escape sequence")
            
            escape_char = self.advance()
            escape_map = {
                'n': '\n',
                't': '\t',
                'r': '\r',
                '\\': '\\',
                '\'': '\'',
                '"': '"',
                '0': '\0'
            }
            value = escape_map.get(escape_char, escape_char)
        else:
            value = self.advance()
        
        if self.peek() != '\'':
            self.error("Character literal must be closed with single quote")
        
        self.advance()  # consume closing quote
        return Token(TokenType.CHAR, value, start_pos[0], start_pos[1])
    
    def read_comment(self) -> Token:
        """Read a single-line comment."""
        start_pos = (self.line, self.column)
        value = ""
        
        # Skip the '//' 
        self.advance()
        self.advance()
        
        while self.peek() and self.peek() != '\n':
            value += self.advance()
        
        return Token(TokenType.COMMENT, value, start_pos[0], start_pos[1])
    
    def tokenize(self) -> List[Token]:
        """Tokenize the entire input text."""
        while self.pos < len(self.text):
            self.skip_whitespace()
            
            if self.pos >= len(self.text):
                break
            
            char = self.peek()
            
            # Newlines
            if char == '\n':
                token = Token(TokenType.NEWLINE, char, self.line, self.column)
                self.tokens.append(token)
                self.advance()
                continue
            
            # Numbers
            if char.isdigit():
                self.tokens.append(self.read_number())
                continue
            
            # Identifiers and keywords
            if char.isalpha() or char == '_':
                self.tokens.append(self.read_identifier())
                continue
            
            # Character literals
            if char == '\'':
                self.tokens.append(self.read_char_literal())
                continue
            
            # Comments
            if char == '/' and self.peek(1) == '/':
                self.tokens.append(self.read_comment())
                continue
            
            # Multi-character operators
            two_char = char + (self.peek(1) or '')
            if two_char in self.OPERATORS:
                token = Token(self.OPERATORS[two_char], two_char, self.line, self.column)
                self.tokens.append(token)
                self.advance()
                self.advance()
                continue
            
            if two_char in self.DELIMITERS:
                token = Token(self.DELIMITERS[two_char], two_char, self.line, self.column)
                self.tokens.append(token)
                self.advance()
                self.advance()
                continue
            
            # Single-character operators and delimiters
            if char in self.OPERATORS:
                token = Token(self.OPERATORS[char], char, self.line, self.column)
                self.tokens.append(token)
                self.advance()
                continue
            
            if char in self.DELIMITERS:
                token = Token(self.DELIMITERS[char], char, self.line, self.column)
                self.tokens.append(token)
                self.advance()
                continue
            
            # Handle * as special symbol for dereference
            if char == '*':
                token = Token(TokenType.ASTERISK, char, self.line, self.column)
                self.tokens.append(token)
                self.advance()
                continue
            
            # Unknown character
            self.error(f"Unexpected character: '{char}'")
        
        # Add EOF token
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens


def tokenize(text: str) -> List[Token]:
    """Convenience function to tokenize MCL source code."""
    lexer = Lexer(text)
    return lexer.tokenize()