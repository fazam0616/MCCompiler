"""MCL Parser

Parses tokens into an Abstract Syntax Tree (AST).
"""

from typing import List, Optional, Union
from .lexer import Token, TokenType, LexerError
from .ast_nodes import *


class ParseError(Exception):
    """Exception raised for parsing errors."""
    def __init__(self, message: str, token: Token):
        super().__init__(f"Parse error at {token.line}:{token.column}: {message}")
        self.token = token


class Parser:
    """MCL Parser - converts tokens to AST."""
    
    def __init__(self, tokens: List[Token]):
        self.tokens = [t for t in tokens if t.type != TokenType.COMMENT]  # Filter comments
        self.current = 0
    
    def error(self, message: str) -> None:
        """Raise a parse error at the current token."""
        token = self.peek()
        raise ParseError(message, token)
    
    def peek(self, offset: int = 0) -> Token:
        """Look ahead at token without consuming it."""
        pos = self.current + offset
        if pos >= len(self.tokens):
            return self.tokens[-1]  # Return EOF token
        return self.tokens[pos]
    
    def advance(self) -> Token:
        """Consume and return the current token."""
        if not self.is_at_end():
            self.current += 1
        return self.previous()
    
    def is_at_end(self) -> bool:
        """Check if we've reached the end of tokens."""
        return self.peek().type == TokenType.EOF
    
    def previous(self) -> Token:
        """Return the previously consumed token."""
        return self.tokens[self.current - 1]
    
    def check(self, token_type: TokenType) -> bool:
        """Check if current token is of given type."""
        if self.is_at_end():
            return False
        return self.peek().type == token_type
    
    def match(self, *types: TokenType) -> bool:
        """Check if current token matches any of the given types."""
        for token_type in types:
            if self.check(token_type):
                self.advance()
                return True
        return False
    
    def consume(self, token_type: TokenType, message: str) -> Token:
        """Consume token of given type or raise error."""
        if self.check(token_type):
            return self.advance()
        
        self.error(message)
    
    def skip_newlines(self) -> None:
        """Skip newline tokens."""
        while self.match(TokenType.NEWLINE):
            pass
    
    def parse(self) -> Program:
        """Parse the entire program."""
        declarations = []
        
        while not self.is_at_end():
            self.skip_newlines()
            if not self.is_at_end():
                decl = self.declaration()
                if decl:
                    declarations.append(decl)
        
        return Program(declarations)
    
    def declaration(self) -> Optional[Statement]:
        """Parse a declaration (function or variable)."""
        try:
            if self.check(TokenType.FUNCTION):
                return self.function_declaration()
            return self.statement()
        except ParseError as e:
            # Synchronize on error
            self.synchronize()
            raise e
    
    def function_declaration(self) -> FunctionDeclaration:
        """Parse function declaration."""
        self.consume(TokenType.FUNCTION, "Expected 'function'")
        
        name = self.consume(TokenType.IDENTIFIER, "Expected function name").value
        
        self.consume(TokenType.LEFT_PAREN, "Expected '(' after function name")
        
        parameters = []
        if not self.check(TokenType.RIGHT_PAREN):
            parameters.append(self.parameter())
            while self.match(TokenType.COMMA):
                parameters.append(self.parameter())
        
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after parameters")
        
        # Optional return type (default to int)
        return_type = IntType()
        # Note: Arrow operator (->) removed from language
        # Functions now have implicit int return type unless specified differently
        
        self.skip_newlines()
        body = self.block_statement()
        
        return FunctionDeclaration(name, parameters, return_type, body)
    
    def parameter(self) -> FunctionParameter:
        """Parse function parameter."""
        name = self.consume(TokenType.IDENTIFIER, "Expected parameter name").value
        param_type = IntType()  # Default type
        
        # Optional type annotation
        if self.match(TokenType.COLON):
            param_type = self.type_annotation()
        
        return FunctionParameter(name, param_type)
    
    def type_annotation(self) -> Type:
        """Parse type annotation."""
        if self.match(TokenType.IDENTIFIER):
            type_name = self.previous().value
            if type_name == "int":
                base_type = IntType()
            elif type_name == "char":
                base_type = IntType()  # For now, char is just int (ASCII)
            elif type_name == "void":
                base_type = VoidType()
            else:
                self.error(f"Unknown type: {type_name}")
            
            # Check for pointer type (type* syntax)
            if self.match(TokenType.ASTERISK):
                return PointerType(base_type)
            
            # Check for array type
            if self.match(TokenType.LEFT_BRACKET):
                if self.check(TokenType.INTEGER):
                    size = int(self.advance().value)
                    self.consume(TokenType.RIGHT_BRACKET, "Expected ']'")
                    return ArrayType(base_type, size)
                else:
                    self.consume(TokenType.RIGHT_BRACKET, "Expected ']'")
                    return ArrayType(base_type)
            
            return base_type
        
        # Default to int
        return IntType()
    
    def statement(self) -> Statement:
        """Parse a statement."""
        if self.match(TokenType.VAR):
            return self.variable_declaration()
        
        # Check for C-style variable declarations (type name = value;)
        if self.is_c_style_declaration():
            return self.c_style_variable_declaration()
            
        if self.match(TokenType.IF):
            return self.if_statement()
        if self.match(TokenType.WHILE):
            return self.while_statement()
        if self.match(TokenType.FOR):
            return self.for_statement()
        if self.match(TokenType.SWITCH):
            return self.switch_statement()
        if self.match(TokenType.RETURN):
            return self.return_statement()
        if self.match(TokenType.BREAK):
            self.consume(TokenType.SEMICOLON, "Expected ';' after 'break'")
            return BreakStatement()
        if self.match(TokenType.CONTINUE):
            self.consume(TokenType.SEMICOLON, "Expected ';' after 'continue'")
            return ContinueStatement()
        if self.match(TokenType.LEFT_BRACE):
            # Delegate to block_statement to ensure consistent block parsing
            # (block_statement will consume the '{' again, so step back one token)
            self.current -= 1
            return self.block_statement()
        
        return self.expression_statement()
    
    def is_c_style_declaration(self) -> bool:
        """Check if current tokens form a C-style declaration (type identifier)."""
        if not self.check(TokenType.IDENTIFIER):
            return False
            
        # Look ahead to see if we have: identifier [*] identifier [=]
        save_current = self.current
        
        # First token should be a type (int)
        type_token = self.peek()
        if type_token.value not in ['int']:
            return False
            
        self.advance()  # consume type
        
        # Check for optional asterisk(s) for pointer types
        while self.check(TokenType.ASTERISK):
            self.advance()
        
        # Next should be identifier (variable name)
        if not self.check(TokenType.IDENTIFIER):
            self.current = save_current
            return False
            
        self.advance()  # consume identifier
        
        # Should be followed by = or ;
        is_declaration = self.check(TokenType.ASSIGN) or self.check(TokenType.SEMICOLON)
        
        # Restore position
        self.current = save_current
        return is_declaration
    
    def c_style_variable_declaration(self) -> VariableDeclaration:
        """Parse C-style variable declaration: type [*] name [= value];"""
        # Parse type (already validated by is_c_style_declaration)
        type_token = self.advance()
        var_type = self.parse_base_type(type_token.value)
        
        # Handle pointer indicators
        while self.match(TokenType.ASTERISK):
            var_type = PointerType(var_type)
        
        # Get variable name
        name = self.consume(TokenType.IDENTIFIER, "Expected variable name").value
        
        # Optional initializer
        initializer = None
        if self.match(TokenType.ASSIGN):
            initializer = self.expression()
        
        self.consume(TokenType.SEMICOLON, "Expected ';' after variable declaration")
        return VariableDeclaration(name, var_type, initializer)
    
    def parse_base_type(self, type_name: str) -> Type:
        """Parse base type from string."""
        if type_name == "int":
            return IntType()
        else:
            raise ParseError(f"Unknown type: {type_name}", self.peek())
    
    def variable_declaration(self) -> VariableDeclaration:
        """Parse variable declaration."""
        name = self.consume(TokenType.IDENTIFIER, "Expected variable name").value
        
        # Optional type annotation
        var_type = IntType()  # Default type
        if self.match(TokenType.COLON):
            var_type = self.type_annotation()
        
        # Optional initializer
        initializer = None
        if self.match(TokenType.ASSIGN):
            initializer = self.expression()
        
        self.consume(TokenType.SEMICOLON, "Expected ';' after variable declaration")
        return VariableDeclaration(name, var_type, initializer)
    
    def if_statement(self) -> IfStatement:
        """Parse if statement with support for else if."""
        self.consume(TokenType.LEFT_PAREN, "Expected '(' after 'if'")
        condition = self.expression()
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after if condition")
        
        self.skip_newlines()
        then_branch = self.statement()
        
        self.skip_newlines()  # Skip newlines/comments before checking for else
        else_branch = None
        if self.match(TokenType.ELSE):
            self.skip_newlines()
            # Check for "else if" pattern
            if self.check(TokenType.IF):
                # This is an "else if" - parse it as a nested if statement
                self.advance()  # consume the 'if'
                else_branch = self.if_statement()
            else:
                # Regular else clause
                else_branch = self.statement()
        
        return IfStatement(condition, then_branch, else_branch)
    
    def while_statement(self) -> WhileStatement:
        """Parse while statement."""
        self.consume(TokenType.LEFT_PAREN, "Expected '(' after 'while'")
        condition = self.expression()
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after while condition")
        
        self.skip_newlines()
        body = self.statement()
        
        return WhileStatement(condition, body)
    
    def for_statement(self) -> ForStatement:
        """Parse for statement."""
        self.consume(TokenType.LEFT_PAREN, "Expected '(' after 'for'")
        
        # Initializer
        initializer = None
        if self.match(TokenType.SEMICOLON):
            initializer = None
        elif self.match(TokenType.VAR):
            initializer = self.variable_declaration()
        else:
            initializer = self.expression_statement()
        
        # Condition
        condition = None
        if not self.check(TokenType.SEMICOLON):
            condition = self.expression()
        self.consume(TokenType.SEMICOLON, "Expected ';' after for loop condition")
        
        # Increment
        increment = None
        if not self.check(TokenType.RIGHT_PAREN):
            increment = self.expression()
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after for clauses")
        
        self.skip_newlines()
        body = self.statement()
        
        return ForStatement(initializer, condition, increment, body)
    
    def switch_statement(self) -> SwitchStatement:
        """Parse switch statement."""
        self.consume(TokenType.LEFT_PAREN, "Expected '(' after 'switch'")
        expression = self.expression()
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after switch expression")
        
        self.skip_newlines()
        self.consume(TokenType.LEFT_BRACE, "Expected '{' after switch expression")
        
        cases = []
        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            self.skip_newlines()
            
            if self.match(TokenType.CASE):
                value = self.expression()
                self.consume(TokenType.COLON, "Expected ':' after case value")
            elif self.match(TokenType.DEFAULT):
                value = None
                self.consume(TokenType.COLON, "Expected ':' after 'default'")
            else:
                break
            
            statements = []
            while (not self.check(TokenType.CASE) and 
                   not self.check(TokenType.DEFAULT) and
                   not self.check(TokenType.RIGHT_BRACE) and
                   not self.is_at_end()):
                self.skip_newlines()
                if (not self.check(TokenType.CASE) and 
                    not self.check(TokenType.DEFAULT) and
                    not self.check(TokenType.RIGHT_BRACE)):
                    statements.append(self.statement())
            
            cases.append(SwitchCase(value, statements))
        
        self.consume(TokenType.RIGHT_BRACE, "Expected '}' after switch cases")
        return SwitchStatement(expression, cases)
    
    def return_statement(self) -> ReturnStatement:
        """Parse return statement."""
        value = None
        if not self.check(TokenType.SEMICOLON):
            value = self.expression()
        
        self.consume(TokenType.SEMICOLON, "Expected ';' after return value")
        return ReturnStatement(value)
    
    def block_statement(self) -> Block:
        """Parse block statement."""
        self.consume(TokenType.LEFT_BRACE, "Expected '{' before block")
        statements = []
        
        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            self.skip_newlines()
            if not self.check(TokenType.RIGHT_BRACE):
                statements.append(self.statement())
        
        self.consume(TokenType.RIGHT_BRACE, "Expected '}' after block")
        return Block(statements)
    
    def expression_statement(self) -> ExpressionStatement:
        """Parse expression statement."""
        expr = self.expression()
        self.consume(TokenType.SEMICOLON, "Expected ';' after expression")
        return ExpressionStatement(expr)
    
    def expression(self) -> Expression:
        """Parse expression."""
        return self.assignment()
    
    def assignment(self) -> Expression:
        """Parse assignment expression."""
        expr = self.logical_or()
        
        if self.match(TokenType.ASSIGN):
            value = self.assignment()
            return AssignmentExpression(expr, value)
        
        return expr
    
    def logical_or(self) -> Expression:
        """Parse logical OR expression."""
        expr = self.logical_and()
        
        while self.match(TokenType.LOGICAL_OR):
            operator = BinaryOperator.LOGICAL_OR
            right = self.logical_and()
            expr = BinaryExpression(expr, operator, right)
        
        return expr
    
    def logical_and(self) -> Expression:
        """Parse logical AND expression."""
        expr = self.bitwise_or()
        
        while self.match(TokenType.LOGICAL_AND):
            operator = BinaryOperator.LOGICAL_AND
            right = self.bitwise_or()
            expr = BinaryExpression(expr, operator, right)
        
        return expr
    
    def bitwise_or(self) -> Expression:
        """Parse bitwise OR expression."""
        expr = self.bitwise_xor()
        
        while self.match(TokenType.BITWISE_OR):
            operator = BinaryOperator.BITWISE_OR
            right = self.bitwise_xor()
            expr = BinaryExpression(expr, operator, right)
        
        return expr
    
    def bitwise_xor(self) -> Expression:
        """Parse bitwise XOR expression."""
        expr = self.bitwise_and()
        
        while self.match(TokenType.BITWISE_XOR):
            operator = BinaryOperator.BITWISE_XOR
            right = self.bitwise_and()
            expr = BinaryExpression(expr, operator, right)
        
        return expr
    
    def bitwise_and(self) -> Expression:
        """Parse bitwise AND expression."""
        expr = self.equality()
        
        while self.match(TokenType.BITWISE_AND):
            operator = BinaryOperator.BITWISE_AND
            right = self.equality()
            expr = BinaryExpression(expr, operator, right)
        
        return expr
    
    def equality(self) -> Expression:
        """Parse equality expression."""
        expr = self.comparison()
        
        while self.match(TokenType.EQUALS, TokenType.NOT_EQUALS):
            operator_map = {
                TokenType.EQUALS: BinaryOperator.EQUALS,
                TokenType.NOT_EQUALS: BinaryOperator.NOT_EQUALS
            }
            operator = operator_map[self.previous().type]
            right = self.comparison()
            expr = BinaryExpression(expr, operator, right)
        
        return expr
    
    def comparison(self) -> Expression:
        """Parse comparison expression."""
        expr = self.shift()
        
        while self.match(TokenType.GREATER_THAN, TokenType.GREATER_EQUAL,
                         TokenType.LESS_THAN, TokenType.LESS_EQUAL):
            operator_map = {
                TokenType.GREATER_THAN: BinaryOperator.GREATER_THAN,
                TokenType.GREATER_EQUAL: BinaryOperator.GREATER_EQUAL,
                TokenType.LESS_THAN: BinaryOperator.LESS_THAN,
                TokenType.LESS_EQUAL: BinaryOperator.LESS_EQUAL
            }
            operator = operator_map[self.previous().type]
            right = self.shift()
            expr = BinaryExpression(expr, operator, right)
        
        return expr
    
    def shift(self) -> Expression:
        """Parse shift expression."""
        expr = self.term()
        
        while self.match(TokenType.SHIFT_LEFT, TokenType.SHIFT_RIGHT):
            operator_map = {
                TokenType.SHIFT_LEFT: BinaryOperator.SHIFT_LEFT,
                TokenType.SHIFT_RIGHT: BinaryOperator.SHIFT_RIGHT
            }
            operator = operator_map[self.previous().type]
            right = self.term()
            expr = BinaryExpression(expr, operator, right)
        
        return expr
    
    def term(self) -> Expression:
        """Parse addition/subtraction and bitwise keyword operations."""
        expr = self.factor()
        
        while self.match(TokenType.PLUS, TokenType.MINUS, TokenType.AND, TokenType.OR, TokenType.XOR):
            operator_map = {
                TokenType.PLUS: BinaryOperator.ADD,
                TokenType.MINUS: BinaryOperator.SUBTRACT,
                TokenType.AND: BinaryOperator.AND,
                TokenType.OR: BinaryOperator.OR,
                TokenType.XOR: BinaryOperator.XOR
            }
            operator = operator_map[self.previous().type]
            right = self.factor()
            expr = BinaryExpression(expr, operator, right)
        
        return expr
    
    def factor(self) -> Expression:
        """Parse multiplication/division expression."""
        expr = self.unary()
        
        while self.match(TokenType.ASTERISK, TokenType.DIVIDE, TokenType.MODULO):
            operators = {
                TokenType.ASTERISK: BinaryOperator.MULTIPLY,
                TokenType.DIVIDE: BinaryOperator.DIVIDE,
                TokenType.MODULO: BinaryOperator.MODULO
            }
            operator = operators[self.previous().type]
            right = self.unary()
            expr = BinaryExpression(expr, operator, right)
        
        return expr
    
    def unary(self) -> Expression:
        """Parse unary expression."""
        if self.match(TokenType.LOGICAL_NOT, TokenType.MINUS, TokenType.BITWISE_NOT,
                     TokenType.AT, TokenType.ASTERISK, TokenType.NOT):
            operator_map = {
                TokenType.LOGICAL_NOT: UnaryOperator.LOGICAL_NOT,
                TokenType.MINUS: UnaryOperator.NEGATE,
                TokenType.BITWISE_NOT: UnaryOperator.BITWISE_NOT,
                TokenType.AT: UnaryOperator.ADDRESS_OF,
                TokenType.ASTERISK: UnaryOperator.DEREFERENCE,
                TokenType.NOT: UnaryOperator.NOT
            }
            operator = operator_map[self.previous().type]
            right = self.unary()
            return UnaryExpression(operator, right)
        
        return self.postfix()
    
    def postfix(self) -> Expression:
        """Parse postfix expression (function calls, array access)."""
        expr = self.primary()
        
        while True:
            if self.match(TokenType.LEFT_PAREN):
                # Function call
                arguments = []
                if not self.check(TokenType.RIGHT_PAREN):
                    arguments.append(self.expression())
                    while self.match(TokenType.COMMA):
                        arguments.append(self.expression())
                
                self.consume(TokenType.RIGHT_PAREN, "Expected ')' after arguments")
                expr = FunctionCall(expr, arguments)
            
            elif self.match(TokenType.LEFT_BRACKET):
                # Array access
                index = self.expression()
                self.consume(TokenType.RIGHT_BRACKET, "Expected ']' after array index")
                expr = ArrayAccess(expr, index)
            
            else:
                break
        
        return expr
    
    def primary(self) -> Expression:
        """Parse primary expression."""
        if self.match(TokenType.INTEGER):
            value = self.previous().value
            if value.startswith('0x'):
                return IntegerLiteral(int(value, 16))
            else:
                return IntegerLiteral(int(value))
        
        if self.match(TokenType.CHAR):
            char = self.previous().value
            return CharLiteral(char)
        
        # Memory management functions
        if self.match(TokenType.MALLOC, TokenType.FREE):
            mem_func = self.previous().value
            self.consume(TokenType.LEFT_PAREN, f"Expected '(' after {mem_func}")
            
            arguments = []
            if not self.check(TokenType.RIGHT_PAREN):
                arguments.append(self.expression())
                while self.match(TokenType.COMMA):
                    arguments.append(self.expression())
            
            self.consume(TokenType.RIGHT_PAREN, f"Expected ')' after {mem_func} arguments")
            return MemoryFunctionCall(mem_func, arguments)
        
        # GPU built-in functions
        if self.match(TokenType.DRAWLINE, TokenType.FILLGRID, TokenType.CLEARGRID,
                        TokenType.LOADSPRITE, TokenType.DRAWSPRITE, TokenType.LOADTEXT,
                        TokenType.DRAWTEXT, TokenType.SCROLLBUFFER,
                        TokenType.SETGPUBUFFER, TokenType.GETGPUBUFFER):
            gpu_func = self.previous().value
            self.consume(TokenType.LEFT_PAREN, f"Expected '(' after {gpu_func}")
            
            arguments = []
            if not self.check(TokenType.RIGHT_PAREN):
                arguments.append(self.expression())
                while self.match(TokenType.COMMA):
                    arguments.append(self.expression())
            
            self.consume(TokenType.RIGHT_PAREN, f"Expected ')' after {gpu_func} arguments")
            return GPUFunctionCall(gpu_func, arguments)
        
        if self.match(TokenType.IDENTIFIER):
            return Identifier(self.previous().value)
        
        if self.match(TokenType.LEFT_PAREN):
            expr = self.expression()
            self.consume(TokenType.RIGHT_PAREN, "Expected ')' after expression")
            return expr
        
        self.error("Expected expression")
    
    def synchronize(self) -> None:
        """Synchronize parser after an error."""
        self.advance()
        
        while not self.is_at_end():
            if self.previous().type == TokenType.SEMICOLON:
                return
            
            if self.peek().type in [TokenType.FUNCTION, TokenType.VAR, TokenType.FOR,
                                   TokenType.IF, TokenType.WHILE, TokenType.RETURN]:
                return
            
            self.advance()


def parse(tokens: List[Token]) -> Program:
    """Convenience function to parse tokens into an AST."""
    parser = Parser(tokens)
    return parser.parse()