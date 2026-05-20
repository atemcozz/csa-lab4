from __future__ import annotations

import compiler.ast as ast


# internal lang types (int, void)
class LangType:
    def __init__(self, name: str, is_array: bool = False):
        self.name = name
        self.is_array = is_array

    def __repr__(self):
        return f"{self.name}[]" if self.is_array else self.name

    def __eq__(self, other):
        if not isinstance(other, LangType):
            return False
        return self.name == other.name and self.is_array == other.is_array


BUILTINS_FUNCTIONS = {"in": LangType("int"), "out": LangType("void")}


class SemanticError(Exception):
    def __init__(self, message: str, faulty_ast_node: ast.ASTNode | None = None):
        super().__init__(message)
        self.faulty_ast_node = faulty_ast_node

    pass


# table for current scope
class SymbolTable:
    def __init__(self):
        self.symbols = {}

    def lookup(self, name: str) -> ast.Declaration | None:
        return self.symbols.get(name)


# stack of scopes
class SymbolStack:
    def __init__(self):
        self.stack = []

    def push(self):
        self.stack.append(SymbolTable())

    def pop(self):
        if not self.stack:
            raise SemanticError("Symbol stack underflow")
        self.stack.pop()

    def declare(self, name: str, value: ast.Declaration):
        if not len(self.stack):
            raise SemanticError("No symbol table to declare in")

        if self.stack[-1].lookup(name):
            raise SemanticError(f'Symbol "{name}" already declared in current scope')

        self.stack[-1].symbols[name] = value

    def lookup(self, name: str) -> ast.Declaration | None:
        for table in reversed(self.stack):
            result = table.lookup(name)
            if result is not None:
                return result
        return None

    def lookup_top(self, name: str):
        if not self.stack:
            return None
        return self.stack[-1].lookup(name)

    def size(self):
        return len(self.stack)


class SemanticAnalyzer:
    def __init__(self):
        self.sym_stack = SymbolStack()

    def analyze_tree(self, node: ast.Program):
        self.sym_stack.push()
        for decl in node.declarations:
            self.analyze_declaration(decl)

    def analyze_function_definition(self, decl: ast.FunctionDefinition):
        if self.sym_stack.size() > 1:
            raise SemanticError("Nested function definitions are not allowed", decl)

        if self.sym_stack.lookup_top(decl.name):
            raise SemanticError(f'Function "{decl.name}" already defined', decl)

        self.sym_stack.declare(decl.name, decl)

        self.sym_stack.push()
        for param in decl.params:
            if self.sym_stack.lookup_top(param.name):
                raise SemanticError(f'Symbol "{param.name}" already declared in current scope', param)
            self.sym_stack.declare(param.name, param)
        self.analyze_compound_statement(decl.body, in_function=True)
        self.sym_stack.pop()

    def analyze_variable_declaration(self, decl: ast.VariableDeclaration):
        if self.sym_stack.lookup_top(decl.name):
            raise SemanticError(f'Symbol "{decl.name}" already declared in current scope', decl)

        initializer = decl.initializer
        if initializer:
            init_type = self.analyze_expression(initializer)
            type_name = decl.decl_type.value if isinstance(decl.decl_type, ast.InternalType) else decl.decl_type.name
            decl_type = LangType(type_name, decl.is_array)
            if init_type != decl_type:
                raise SemanticError(f"Type mismatch in initializer: expected {decl_type}, got {init_type}", decl)

        self.sym_stack.declare(decl.name, decl)

    def analyze_declaration(self, decl: ast.Declaration):
        if isinstance(decl, ast.FunctionDefinition):
            self.analyze_function_definition(decl)
        elif isinstance(decl, ast.VariableDeclaration):
            self.analyze_variable_declaration(decl)

    def analyze_compound_statement(self, stmt: ast.CompoundStatement, in_function=False):
        if not in_function:
            self.sym_stack.push()
        for item in stmt.body:
            if isinstance(item, ast.Declaration):
                self.analyze_declaration(item)
            elif isinstance(item, ast.Statement):
                self.analyze_statement(item)
        if not in_function:
            self.sym_stack.pop()

    def analyze_assign_statement(self, stmt: ast.AssignStatement):
        if isinstance(stmt.target, ast.Identifier):
            target_type = self.analyze_identifier(stmt.target)
        elif isinstance(stmt.target, ast.IndexExpression):
            target_type = self.analyze_index_expression(stmt.target)
        else:
            target_type = None

        value_type = self.analyze_expression(stmt.value)
        if target_type != value_type:
            raise SemanticError(f"Type mismatch in assignment: cannot assign {value_type} to {target_type}", stmt)

    def analyze_statement(self, stmt: ast.Statement):
        if isinstance(stmt, ast.ExpressionStatement):
            if stmt.expression:
                self.analyze_expression(stmt.expression)
        elif isinstance(stmt, ast.ReturnStatement):
            if stmt.value:
                self.analyze_expression(stmt.value)
        elif isinstance(stmt, ast.AssignStatement):
            self.analyze_assign_statement(stmt)

    def analyze_expression(self, expr: ast.Expression) -> LangType:
        if not expr:
            return LangType("void")

        if type(expr) in (ast.IntLiteral, ast.CharLiteral):
            return LangType("int")
        if type(expr) is ast.StringLiteral:
            return LangType("int", is_array=True)

        handlers = {
            ast.Identifier: self.analyze_identifier,
            ast.IndexExpression: self.analyze_index_expression,
            ast.BinaryExpression: self.analyze_binary_expression,
            ast.CallExpression: self.analyze_call_expression,
            ast.UnaryExpression: self.analyze_unary_expression,
        }

        handler = handlers.get(type(expr))
        return handler(expr) if handler else LangType("void")

    def analyze_unary_expression(self, expr: ast.UnaryExpression) -> LangType:
        operand_type = self.analyze_expression(expr.operand)
        if operand_type.is_array:
            raise SemanticError("Unsupported operation", expr)
        return operand_type

    def analyze_identifier(self, expr: ast.Identifier) -> LangType:
        decl = self.sym_stack.lookup(expr.name)
        if not decl:
            raise SemanticError(f"Use of undeclared variable '{expr.name}'", expr)

        type_name = decl.decl_type.value if isinstance(decl.decl_type, ast.InternalType) else decl.decl_type.name
        return LangType(type_name, decl.is_array)

    def analyze_binary_expression(self, expr: ast.BinaryExpression) -> LangType:
        l_type = self.analyze_expression(expr.left)
        r_type = self.analyze_expression(expr.right)

        if l_type != r_type:
            raise SemanticError(f"Type mismatch in binary expression: {l_type} {expr.op.value} {r_type}", expr)
        if l_type.is_array:
            raise SemanticError("Cannot perform binary operations on arrays", expr)

        return l_type

    def analyze_index_expression(self, expr: ast.IndexExpression) -> LangType:
        decl = self.sym_stack.lookup(expr.name)
        if not decl:
            raise SemanticError(f"Use of undeclared array '{expr.name}'", expr)

        type_name = decl.decl_type.value if isinstance(decl.decl_type, ast.InternalType) else decl.decl_type.name
        array_type = LangType(type_name, decl.is_array)

        if not array_type.is_array:
            raise SemanticError(f"Cannot index non-array type '{expr.name}'", expr)

        index_type = self.analyze_expression(expr.index)
        if index_type != LangType("int"):
            raise SemanticError(f"Array index must be an integer, got {index_type}", expr.index)

        return LangType(array_type.name, False)

    def analyze_call_expression(self, expr: ast.CallExpression):
        if expr.name in BUILTINS_FUNCTIONS:
            return BUILTINS_FUNCTIONS[expr.name]

        decl = self.sym_stack.lookup(expr.name)
        if not decl:
            raise SemanticError(f"Call to undefined function '{expr.name}'", expr)
        if not isinstance(decl, ast.FunctionDefinition):
            raise SemanticError(f"'{expr.name}' is not a function", expr)

        if len(expr.args) != len(decl.params):
            raise SemanticError("Wrong arguments amount", expr)

        for i, arg in enumerate(expr.args):
            arg_type = self.analyze_expression(arg)
            param = decl.params[i]
            param_type_name = (
                param.decl_type.value if isinstance(param.decl_type, ast.InternalType) else param.decl_type.name
            )
            param_type = LangType(param_type_name, param.is_array)

            if arg_type != param_type:
                raise SemanticError(f"Argument {i+1} type mismatch", arg)

        type_name = decl.decl_type.value if isinstance(decl.decl_type, ast.InternalType) else decl.decl_type.name
        return LangType(type_name, False)
