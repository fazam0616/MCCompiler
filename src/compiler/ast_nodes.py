"""MCL Abstract Syntax Tree Node Definitions

Defines the AST node classes for representing parsed MCL programs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Union, Any
from enum import Enum


class ASTNode(ABC):
    """Base class for all AST nodes."""
    
    @abstractmethod
    def accept(self, visitor):
        """Accept a visitor for the visitor pattern."""
        pass


class Expression(ASTNode):
    """Base class for all expressions."""
    pass


class Statement(ASTNode):
    """Base class for all statements."""
    pass


class Type(ASTNode):
    """Base class for type annotations."""
    pass


# Types
@dataclass
class IntType(Type):
    """Integer type."""
    
    def accept(self, visitor):
        return visitor.visit_int_type(self)


@dataclass
class VoidType(Type):
    """Void type (no return value)."""
    
    def accept(self, visitor):
        return visitor.visit_void_type(self)


@dataclass
class PointerType(Type):
    """Pointer type."""
    target_type: Type
    
    def accept(self, visitor):
        return visitor.visit_pointer_type(self)


@dataclass
class ArrayType(Type):
    """Array type."""
    element_type: Type
    size: Optional[int] = None  # None for dynamic arrays
    
    def accept(self, visitor):
        return visitor.visit_array_type(self)


@dataclass
class FunctionType(Type):
    """Function type."""
    return_type: Type
    parameter_types: List[Type]
    
    def accept(self, visitor):
        return visitor.visit_function_type(self)


# Expressions
@dataclass
class IntegerLiteral(Expression):
    """Integer literal expression."""
    value: int
    
    def accept(self, visitor):
        return visitor.visit_integer_literal(self)


@dataclass
class CharLiteral(Expression):
    """Character literal expression."""
    value: str  # Single character
    
    def accept(self, visitor):
        return visitor.visit_char_literal(self)


@dataclass
class Identifier(Expression):
    """Variable or function identifier."""
    name: str
    
    def accept(self, visitor):
        return visitor.visit_identifier(self)


class BinaryOperator(Enum):
    ADD = "+"
    SUBTRACT = "-"
    MULTIPLY = "*"
    DIVIDE = "/"
    MODULO = "%"
    EQUALS = "=="
    NOT_EQUALS = "!="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    LESS_EQUAL = "<="
    GREATER_EQUAL = ">="
    LOGICAL_AND = "&&"
    LOGICAL_OR = "||"
    BITWISE_AND = "&"
    BITWISE_OR = "|"
    BITWISE_XOR = "^"
    SHIFT_LEFT = "<<"
    SHIFT_RIGHT = ">>"
    # Keyword-based bitwise operations
    AND = "and"
    OR = "or"
    XOR = "xor"


@dataclass
class BinaryExpression(Expression):
    """Binary operation expression."""
    left: Expression
    operator: BinaryOperator
    right: Expression
    
    def accept(self, visitor):
        return visitor.visit_binary_expression(self)


class UnaryOperator(Enum):
    NEGATE = "-"
    LOGICAL_NOT = "!"
    BITWISE_NOT = "~"
    ADDRESS_OF = "&"
    DEREFERENCE = "*"
    # Keyword-based NOT operation
    NOT = "not"


@dataclass
class UnaryExpression(Expression):
    """Unary operation expression."""
    operator: UnaryOperator
    operand: Expression
    
    def accept(self, visitor):
        return visitor.visit_unary_expression(self)


@dataclass
class AssignmentExpression(Expression):
    """Assignment expression."""
    target: Expression
    value: Expression
    
    def accept(self, visitor):
        return visitor.visit_assignment_expression(self)


@dataclass
class FunctionCall(Expression):
    """Function call expression."""
    function: Expression
    arguments: List[Expression]
    
    def accept(self, visitor):
        return visitor.visit_function_call(self)


@dataclass
class GPUFunctionCall(Expression):
    """GPU built-in function call expression."""
    function_name: str
    arguments: List[Expression]
    
    def accept(self, visitor):
        return visitor.visit_gpu_function_call(self)


@dataclass
class MemoryFunctionCall(Expression):
    """Memory management function call (malloc, free)."""
    function_name: str  # "malloc" or "free"
    arguments: List[Expression]
    
    def accept(self, visitor):
        return visitor.visit_memory_function_call(self)


@dataclass
class ArrayAccess(Expression):
    """Array element access expression."""
    array: Expression
    index: Expression
    
    def accept(self, visitor):
        return visitor.visit_array_access(self)


# Statements
@dataclass
class ExpressionStatement(Statement):
    """Expression used as a statement."""
    expression: Expression
    
    def accept(self, visitor):
        return visitor.visit_expression_statement(self)


@dataclass
class VariableDeclaration(Statement):
    """Variable declaration statement."""
    name: str
    var_type: Type
    initializer: Optional[Expression] = None
    
    def accept(self, visitor):
        return visitor.visit_variable_declaration(self)


@dataclass
class Block(Statement):
    """Block statement containing multiple statements."""
    statements: List[Statement]
    
    def accept(self, visitor):
        return visitor.visit_block(self)


@dataclass
class IfStatement(Statement):
    """If statement with optional else clause."""
    condition: Expression
    then_branch: Statement
    else_branch: Optional[Statement] = None
    
    def accept(self, visitor):
        return visitor.visit_if_statement(self)


@dataclass
class WhileStatement(Statement):
    """While loop statement."""
    condition: Expression
    body: Statement
    
    def accept(self, visitor):
        return visitor.visit_while_statement(self)


@dataclass
class ForStatement(Statement):
    """For loop statement."""
    initializer: Optional[Statement]
    condition: Optional[Expression]
    increment: Optional[Expression]
    body: Statement
    
    def accept(self, visitor):
        return visitor.visit_for_statement(self)


@dataclass
class SwitchCase:
    """Single case in a switch statement."""
    value: Optional[Expression]  # None for default case
    statements: List[Statement]


@dataclass
class SwitchStatement(Statement):
    """Switch statement."""
    expression: Expression
    cases: List[SwitchCase]
    
    def accept(self, visitor):
        return visitor.visit_switch_statement(self)


@dataclass
class ReturnStatement(Statement):
    """Return statement."""
    value: Optional[Expression] = None
    
    def accept(self, visitor):
        return visitor.visit_return_statement(self)


@dataclass
class BreakStatement(Statement):
    """Break statement."""
    
    def accept(self, visitor):
        return visitor.visit_break_statement(self)


@dataclass
class ContinueStatement(Statement):
    """Continue statement."""
    
    def accept(self, visitor):
        return visitor.visit_continue_statement(self)


@dataclass
class FunctionParameter:
    """Function parameter definition."""
    name: str
    param_type: Type


@dataclass
class FunctionDeclaration(Statement):
    """Function declaration statement."""
    name: str
    parameters: List[FunctionParameter]
    return_type: Type
    body: Block
    
    def accept(self, visitor):
        return visitor.visit_function_declaration(self)


@dataclass
class Program(ASTNode):
    """Root AST node representing the entire program."""
    declarations: List[Statement]
    
    def accept(self, visitor):
        return visitor.visit_program(self)


# Visitor interface
class ASTVisitor(ABC):
    """Abstract visitor for AST traversal."""
    
    @abstractmethod
    def visit_program(self, node: Program): pass
    
    @abstractmethod
    def visit_function_declaration(self, node: FunctionDeclaration): pass
    
    @abstractmethod
    def visit_variable_declaration(self, node: VariableDeclaration): pass
    
    @abstractmethod
    def visit_block(self, node: Block): pass
    
    @abstractmethod
    def visit_expression_statement(self, node: ExpressionStatement): pass
    
    @abstractmethod
    def visit_if_statement(self, node: IfStatement): pass
    
    @abstractmethod
    def visit_while_statement(self, node: WhileStatement): pass
    
    @abstractmethod
    def visit_for_statement(self, node: ForStatement): pass
    
    @abstractmethod
    def visit_switch_statement(self, node: SwitchStatement): pass
    
    @abstractmethod
    def visit_return_statement(self, node: ReturnStatement): pass
    
    @abstractmethod
    def visit_break_statement(self, node: BreakStatement): pass
    
    @abstractmethod
    def visit_continue_statement(self, node: ContinueStatement): pass
    
    @abstractmethod
    def visit_binary_expression(self, node: BinaryExpression): pass
    
    @abstractmethod
    def visit_unary_expression(self, node: UnaryExpression): pass
    
    @abstractmethod
    def visit_assignment_expression(self, node: AssignmentExpression): pass
    
    @abstractmethod
    def visit_function_call(self, node: FunctionCall): pass
    
    @abstractmethod
    def visit_gpu_function_call(self, node: GPUFunctionCall): pass
    
    @abstractmethod
    def visit_memory_function_call(self, node: MemoryFunctionCall): pass
    
    @abstractmethod
    def visit_array_access(self, node: ArrayAccess): pass
    
    @abstractmethod
    def visit_integer_literal(self, node: IntegerLiteral): pass
    
    @abstractmethod
    def visit_char_literal(self, node: CharLiteral): pass
    
    @abstractmethod
    def visit_identifier(self, node: Identifier): pass
    
    @abstractmethod
    def visit_int_type(self, node: IntType): pass
    
    @abstractmethod
    def visit_pointer_type(self, node: PointerType): pass
    
    @abstractmethod
    def visit_array_type(self, node: ArrayType): pass
    
    @abstractmethod
    def visit_function_type(self, node: FunctionType): pass