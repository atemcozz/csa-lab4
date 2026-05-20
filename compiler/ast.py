from __future__ import annotations

from enum import Enum

from compiler.lexer import Token


class InternalType(Enum):
    INT = "int"
    VOID = "void"


# store start token for error messages and debugging


class ASTNode:
    def __init__(self, start_token: Token):
        self.start_token = start_token

    def __repr__(self):
        return f"ASTNode(start_token={self.start_token})"


class Expression(ASTNode):
    pass


class Statement(ASTNode):
    pass


class Declaration(ASTNode):
    decl_type: InternalType | Identifier
    is_array: bool

    def __init__(self, start_token: Token, name: str):
        super().__init__(start_token)
        self.name = name


class Program(ASTNode):
    def __init__(self, declarations: list[Declaration], start_token: Token):
        super().__init__(start_token)
        self.declarations = declarations

    def __repr__(self):
        return f"Program({', '.join(repr(d) for d in self.declarations)})"


class InterruptMarker(ASTNode):
    def __init__(self, number: int, start_token: Token):
        super().__init__(start_token)
        self.number = number

    def __repr__(self):
        return f"InterruptMarker({self.number})"


class Parameter(Declaration):
    def __init__(self, param_type: InternalType | Identifier, name: str, is_array: bool, start_token: Token):
        super().__init__(start_token, name)
        self.decl_type = param_type
        self.is_array = is_array

    def __repr__(self):
        return f"Parameter({self.decl_type}, array={self.is_array}, {self.name})"


class CompoundStatement(Statement):
    def __init__(self, body: list[VariableDeclaration | Statement], start_token: Token):
        super().__init__(start_token)
        self.body = body

    def __repr__(self):
        inner = ", ".join(repr(s) for s in self.body)
        return f"CompoundStatement({inner})"


class FunctionDefinition(Declaration):
    def __init__(
        self,
        func_type: InternalType | Identifier,
        name: str,
        params: list[Parameter],
        body: CompoundStatement,
        start_token: Token,
        interrupt: InterruptMarker | None = None,
    ):
        super().__init__(start_token, name)
        self.decl_type = func_type
        self.is_array = False
        self.params = params
        self.body = body
        self.interrupt = interrupt

    def __repr__(self):
        interrupt = f"interrupt={self.interrupt}, " if self.interrupt else ""
        params = ", ".join(repr(p) for p in self.params)
        return f"FunctionDefinition({interrupt}{self.decl_type} {self.name}({params}), {self.body})"


class VariableDeclaration(Declaration):
    def __init__(
        self,
        var_type: InternalType | Identifier,
        is_array: bool,
        name: str,
        start_token: Token,
        initializer: Expression | None = None,
        array_size: int | None = None,
    ):
        super().__init__(start_token, name)
        self.decl_type = var_type
        self.is_array = is_array
        self.array_size = array_size
        self.initializer = initializer

    def __repr__(self):
        if self.is_array:
            if self.array_size and not self.initializer:
                return f"VariableDeclaration({self.decl_type} {self.name}[{self.array_size}])"
            if self.initializer and not self.array_size:
                return f"VariableDeclaration({self.decl_type} {self.name}[] = {self.initializer})"
        if self.initializer:
            return f"VariableDeclaration({self.decl_type} {self.name} = {self.initializer})"
        return f"VariableDeclaration({self.decl_type} {self.name})"


class AssignStatement(Statement):
    def __init__(self, target: Identifier | IndexExpression, value: Expression, start_token: Token):
        super().__init__(start_token)
        self.target = target
        self.value = value

    def __repr__(self):
        return f"AssignStatement({self.target} = {self.value})"


class ExpressionStatement(Statement):
    def __init__(self, start_token: Token, expression: Expression | None = None):
        super().__init__(start_token)
        self.expression = expression

    def __repr__(self):
        return f"ExpressionStatement({self.expression})"


class IfStatement(Statement):
    def __init__(
        self, condition: Expression, then_body: Statement, start_token: Token, else_body: Statement | None = None
    ):
        super().__init__(start_token)
        self.condition = condition
        self.then_body = then_body
        self.else_body = else_body

    def __repr__(self):
        if self.else_body:
            return f"IfStatement({self.condition}, then={self.then_body}, else={self.else_body})"
        return f"IfStatement({self.condition}, then={self.then_body})"


class WhileStatement(Statement):
    def __init__(self, condition: Expression, body: Statement, start_token: Token):
        super().__init__(start_token)
        self.condition = condition
        self.body = body

    def __repr__(self):
        return f"WhileStatement({self.condition}, {self.body})"


class ReturnStatement(Statement):
    def __init__(self, start_token: Token, value: Expression | None = None):
        super().__init__(start_token)
        self.value = value

    def __repr__(self):
        return f"ReturnStatement({self.value})"


class BinaryExpression(Expression):
    def __init__(self, op_token: Token, left: Expression, right: Expression, start_token: Token):
        super().__init__(start_token)
        self.op = op_token
        self.left = left
        self.right = right

    def __repr__(self):
        return f"BinaryExpression({self.left} {self.op.value} {self.right})"


class UnaryExpression(Expression):
    def __init__(self, op_token: Token, operand: Expression, start_token: Token):
        super().__init__(start_token)
        self.op = op_token
        self.operand = operand

    def __repr__(self):
        return f"UnaryExpression({self.op.value}{self.operand})"


class CallExpression(Expression):
    def __init__(self, name: str, args: list[Expression], start_token: Token):
        super().__init__(start_token)
        self.name = name
        self.args = args

    def __repr__(self):
        args = ", ".join(repr(a) for a in self.args)
        return f"CallExpression({self.name}({args}))"


class IndexExpression(Expression):
    def __init__(self, name: str, index: Expression, start_token: Token):
        super().__init__(start_token)
        self.name = name
        self.index = index

    def __repr__(self):
        return f"IndexExpression({self.name}[{self.index}])"


class Identifier(Expression):
    def __init__(self, name: str, start_token: Token):
        super().__init__(start_token)
        self.name = name

    def __repr__(self):
        return f"Identifier({self.name})"


class IntLiteral(Expression):
    def __init__(self, value: int, start_token: Token):
        super().__init__(start_token)
        self.value = value

    def __repr__(self):
        return f"IntLiteral({self.value})"


class CharLiteral(Expression):
    def __init__(self, value: str, start_token: Token):
        super().__init__(start_token)
        self.value = value

    def __repr__(self):
        return f"CharLiteral('{self.value!r}')"


class StringLiteral(Expression):
    def __init__(self, value: str, start_token: Token):
        super().__init__(start_token)
        self.value = value

    def __repr__(self):
        return f'StringLiteral("{self.value!r}")'
