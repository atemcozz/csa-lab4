from __future__ import annotations

import compiler.ast as ast
from compiler.semantic_analyzer import SymbolStack


class IRGenerationError(Exception):
    def __init__(self, message: str, faulty_ast_node: ast.ASTNode | None = None):
        super().__init__(message)
        self.faulty_ast_node = faulty_ast_node


class IRNode:
    pass


class Assign(IRNode):
    def __init__(self, dest, src):
        self.dest = dest
        self.src = src

    def __repr__(self):
        return f"Assign({self.dest} = {self.src})"


class BinOp(IRNode):
    def __init__(self, dest, left, op, right):
        self.dest = dest
        self.left = left
        self.op = op
        self.right = right

    def __repr__(self):
        return f"BinOp({self.dest} = {self.left} {self.op} {self.right})"


class UnaryOp(IRNode):
    def __init__(self, dest, op, operand):
        self.dest = dest
        self.op = op
        self.operand = operand

    def __repr__(self):
        return f"UnaryOp({self.dest} = {self.op}{self.operand})"


class Label(IRNode):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"\n{self.name}:"


class Jump(IRNode):
    def __init__(self, label: Label):
        self.target = label

    def __repr__(self):
        return f"Jump({self.target.name})"


# jump if condition is false
class CondJump(IRNode):
    def __init__(self, condition, label: Label):
        self.condition = condition
        self.target = label

    def __repr__(self):
        return f"CondJump(if !{self.condition} goto {self.target.name})"


class Call(IRNode):
    def __init__(self, dest, name, args):
        self.dest = dest
        self.func_name = name
        self.args = args

    def __repr__(self):
        args_str = ", ".join(str(a) for a in self.args)
        return f"Call({self.dest} = {self.func_name}({args_str}))"


class Return(IRNode):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"Return({self.value})"


class Store(IRNode):
    def __init__(self, value, imm, address):
        self.value = value
        self.imm = imm
        self.address = address

    def __repr__(self):
        return f"Store(mem[{self.address}+{self.imm}] = {self.value})"


class Load(IRNode):
    def __init__(self, dest: str, address: str, imm: str):
        self.dest = dest
        self.address = address
        self.imm = imm

    def __repr__(self):
        return f"Load({self.dest} = mem[{self.address}+{self.imm}])"


# for stack array allocation
class LocalArrayAlloc(IRNode):
    def __init__(self, name: str, size: int):
        self.name = name
        self.size = size

    def __repr__(self):
        return f"LocalArrayAlloc({self.name}[{self.size}])"


class GlobalVariable(IRNode):
    def __init__(self, name, initializer=None):
        self.name = name
        self.initializer = initializer

    def __repr__(self):
        if self.initializer:
            return f"GlobalVariable({self.name} = {self.initializer})"
        return f"GlobalVariable({self.name})"


class GlobalArray(IRNode):
    def __init__(self, name: str, size: int, label: str | None = None):
        self.name = name
        self.size = size
        self.label = label

    def __repr__(self):
        if self.label:
            return f"GlobalArray({self.name}[{self.size}], label={self.label})"
        return f"GlobalArray({self.name}[{self.size}])"


class StringData(IRNode):
    def __init__(self, name: str, value: str):
        self.name = name
        self.value = value

    def __repr__(self):
        return f"StringData({self.name}: {self.value!r})"


# in/out instructions


class ReadIO(IRNode):
    def __init__(self, dest, port):
        self.dest = dest
        self.port = port

    def __repr__(self):
        return f"ReadIO({self.dest} = in(port: {self.port}))"


class WriteIO(IRNode):
    def __init__(self, value, port):
        self.value = value
        self.port = port

    def __repr__(self):
        return f"WriteIO(out(value: {self.value}, port: {self.port}))"


class Program:
    def __init__(self, instructions: list[IRNode], data: list[IRNode], interrupt_table: dict, entry_point: str):
        self.instructions = instructions
        self.data = data
        self.interrupt_table = interrupt_table
        self.entry_point = entry_point


class IRGenerator:
    def __init__(self):
        self.instructions = []
        self.sym_stack = SymbolStack()
        self.var_counter = 0
        self.label_counter = 0
        self.string_counter = 0
        self.if_counter = 0
        self.while_counter = 0
        self.interrupt_table = {}
        self.data = []

    def push_node(self, node: IRNode):
        self.instructions.append(node)

    def new_temp_var(self):
        name = f"${self.var_counter}"
        self.var_counter += 1
        return name

    def new_label(self):
        name = f"label_{self.label_counter}"
        self.label_counter += 1
        return name

    def new_string_label(self):
        name = f"str_{self.string_counter}"
        self.string_counter += 1
        return name

    def new_if_label(self):
        name = f"if_{self.if_counter}"
        self.if_counter += 1
        return name

    def new_while_label(self):
        name = f"while_{self.while_counter}"
        self.while_counter += 1
        return name

    def generate_from_ast(self, ast_root: ast.Program, entry_point: str):
        self.sym_stack.push()
        for decl in ast_root.declarations:
            self.push_ext_declarations(decl)

        return Program(self.instructions, self.data, self.interrupt_table, entry_point)

    def push_ext_declarations(self, decl: ast.Declaration):
        if isinstance(decl, ast.FunctionDefinition):
            self.push_function(decl)
        elif isinstance(decl, ast.VariableDeclaration):
            self.push_variable_declaration(decl, is_global=True)
        else:
            raise IRGenerationError(f"Unimplemented declaration type: {type(decl)}", decl)

    def push_literal_expression(self, expr):
        if isinstance(expr, ast.IntLiteral):
            temp_var = self.new_temp_var()
            self.push_node(Assign(temp_var, expr.value))
            return temp_var
        if isinstance(expr, ast.CharLiteral):
            temp_var = self.new_temp_var()
            self.push_node(Assign(temp_var, ord(expr.value)))
            return temp_var
        if isinstance(expr, ast.StringLiteral):
            label_str = self.new_string_label()
            self.data.append(StringData(label_str, expr.value))
            temp_var = self.new_temp_var()
            self.push_node(Assign(temp_var, label_str))
            return temp_var
        raise IRGenerationError(f"Unimplemented literal type: {type(expr)}", expr)

    def push_op_expression(self, expr):
        if isinstance(expr, ast.BinaryExpression):
            left = self.push_expression(expr.left)
            right = self.push_expression(expr.right)
            temp_var = self.new_temp_var()
            self.push_node(BinOp(temp_var, left, expr.op.value, right))
            return temp_var
        if isinstance(expr, ast.UnaryExpression):
            operand = self.push_expression(expr.operand)
            temp_var = self.new_temp_var()
            self.push_node(UnaryOp(temp_var, expr.op.value, operand))
            return temp_var
        raise IRGenerationError(f"Unimplemented op type: {type(expr)}", expr)

    def push_call_expression(self, expr: ast.CallExpression):
        if expr.name == "in":
            if len(expr.args) != 1:
                raise IRGenerationError("in() function takes exactly one argument", expr)
            port = self.push_expression(expr.args[0])
            temp_var = self.new_temp_var()
            node = ReadIO(temp_var, port)
            self.push_node(node)
            return temp_var

        if expr.name == "out":
            if len(expr.args) != 2:
                raise IRGenerationError("out() function takes exactly two arguments", expr)
            value = self.push_expression(expr.args[0])
            port = self.push_expression(expr.args[1])
            node = WriteIO(value, port)
            self.push_node(node)
            return None
        args = [self.push_expression(arg) for arg in expr.args]
        temp_var = self.new_temp_var()
        node = Call(temp_var, f"function_{expr.name}", args)
        self.push_node(node)
        return temp_var

    def push_expression(self, expr):
        if isinstance(expr, (ast.IntLiteral, ast.CharLiteral, ast.StringLiteral)):
            return self.push_literal_expression(expr)
        if isinstance(expr, ast.Identifier):
            return expr.name
        if isinstance(expr, ast.IndexExpression):
            index = self.push_expression(expr.index)
            if not index:
                raise IRGenerationError("Array index cannot be void", expr.index)
            temp_var = self.new_temp_var()
            self.push_node(Load(temp_var, expr.name, index))
            return temp_var
        if isinstance(expr, (ast.BinaryExpression, ast.UnaryExpression)):
            return self.push_op_expression(expr)
        if isinstance(expr, ast.CallExpression):
            return self.push_call_expression(expr)
        raise IRGenerationError(f"Unimplemented expression type: {type(expr)}", expr)

    def push_statement(self, stmt):
        if isinstance(stmt, ast.AssignStatement):
            self.push_assignment_statement(stmt)
        elif isinstance(stmt, ast.ExpressionStatement):
            self.push_expression_statement(stmt)
        elif isinstance(stmt, ast.CompoundStatement):
            self.push_compound_statement(stmt)
        elif isinstance(stmt, ast.IfStatement):
            self.push_if_statement(stmt)
        elif isinstance(stmt, ast.WhileStatement):
            self.push_while_statement(stmt)
        elif isinstance(stmt, ast.ReturnStatement):
            self.push_return_statement(stmt)
        else:
            raise IRGenerationError(f"Unimplemented statement type: {type(stmt)}", stmt)

    def push_expression_statement(self, stmt: ast.ExpressionStatement):
        if stmt.expression:
            self.push_expression(stmt.expression)

    def push_assignment_statement(self, stmt: ast.AssignStatement):
        if isinstance(stmt.target, ast.Identifier):
            decl = self.sym_stack.lookup(stmt.target.name)
            if not decl:
                raise IRGenerationError(f"Use of undeclared variable '{stmt.target.name}'", stmt.target)
            value = self.push_expression(stmt.value)
            self.push_node(Assign(stmt.target.name, value))

        elif isinstance(stmt.target, ast.IndexExpression):
            decl = self.sym_stack.lookup(stmt.target.name)
            if not decl:
                raise IRGenerationError(f"Use of undeclared array '{stmt.target.name}'", stmt.target)

            value = self.push_expression(stmt.value)
            index = self.push_expression(stmt.target.index)

            self.push_node(Store(value, index, stmt.target.name))

    def push_global_variable_declaration(self, decl: ast.VariableDeclaration):
        if decl.is_array:
            if decl.array_size:
                self.data.append(GlobalArray(decl.name, decl.array_size))
            else:
                initializer = decl.initializer
                if not isinstance(initializer, ast.StringLiteral):
                    raise IRGenerationError(
                        "Only string literals can be used to initialize global arrays without specified size",
                        decl.initializer,
                    )
                self.data.append(StringData(decl.name, initializer.value))
        else:
            if isinstance(decl.initializer, ast.IntLiteral):
                self.data.append(GlobalVariable(decl.name, decl.initializer.value))
            elif isinstance(decl.initializer, ast.CharLiteral):
                self.data.append(GlobalVariable(decl.name, ord(decl.initializer.value)))
            else:
                self.data.append(GlobalVariable(decl.name, 0))

    def push_local_variable_declaration(self, decl: ast.VariableDeclaration):
        if decl.is_array:
            initializer = decl.initializer
            if initializer and isinstance(initializer, ast.StringLiteral):
                string_data = StringData(self.new_string_label(), initializer.value)
                self.data.append(string_data)
                self.push_node(Assign(decl.name, string_data.name))
            else:
                self.push_node(LocalArrayAlloc(decl.name, decl.array_size or 0))
        else:
            if decl.initializer:
                value = self.push_expression(decl.initializer)
                self.push_node(Assign(decl.name, value))

    def push_variable_declaration(self, decl: ast.VariableDeclaration, is_global=False):
        if is_global:
            self.push_global_variable_declaration(decl)
        else:
            self.push_local_variable_declaration(decl)
        self.sym_stack.declare(decl.name, decl)

    def get_local_arrays(self):
        result = []
        for scope in self.sym_stack.stack[1:]:
            for decl in scope.symbols.values():
                if isinstance(decl, ast.VariableDeclaration) and decl.is_array:
                    if not (decl.initializer and isinstance(decl.initializer, ast.StringLiteral)):
                        result.append(decl)
        return result

    def push_compound_statement(self, stmt: ast.CompoundStatement):
        self.sym_stack.push()

        local_arrays = []
        for el in stmt.body:
            if isinstance(el, ast.VariableDeclaration):
                self.push_variable_declaration(el, is_global=False)
                if el.is_array and not (el.initializer and isinstance(el.initializer, ast.StringLiteral)):
                    local_arrays.append(el)
            elif isinstance(el, ast.ReturnStatement):
                self.push_compound_stmt_return(el)
                break
            else:
                self.push_statement(el)

        self.sym_stack.pop()

    def push_compound_stmt_return(self, el: ast.ReturnStatement):
        value_var = self.push_expression(el.value) if el.value else None
        self.push_node(Return(value_var))

    def push_function(self, func_def: ast.FunctionDefinition):
        label = Label(f"function_{func_def.name}")
        self.push_node(label)

        self.sym_stack.push()

        for param in func_def.params:
            self.sym_stack.declare(param.name, param)

        self.push_compound_statement(func_def.body)

        self.push_node(Return(None))

        self.sym_stack.pop()

        if func_def.interrupt is not None:
            self.interrupt_table[func_def.interrupt.number] = label.name

    def push_if_statement(self, if_stmt: ast.IfStatement):
        cond_var = self.push_expression(if_stmt.condition)
        label_postfix = self.new_if_label()
        else_label = Label(f"{label_postfix}_else") if if_stmt.else_body else None
        end_label = Label(f"{label_postfix}_endif")

        self.push_node(CondJump(cond_var, else_label or end_label))

        self.push_statement(if_stmt.then_body)
        self.push_node(Jump(end_label))

        if if_stmt.else_body and else_label:
            self.push_node(else_label)
            self.push_statement(if_stmt.else_body)

        self.push_node(end_label)

    def push_while_statement(self, while_stmt: ast.WhileStatement):
        label_postfix = self.new_while_label()
        cond_label = Label(f"{label_postfix}_cond")
        end_label = Label(f"{label_postfix}_end")

        self.push_node(cond_label)

        cond_var = self.push_expression(while_stmt.condition)
        self.push_node(CondJump(cond_var, end_label))

        self.push_statement(while_stmt.body)

        self.push_node(Jump(cond_label))

        self.push_node(end_label)

    def push_return_statement(self, return_stmt: ast.ReturnStatement):
        value_var = self.push_expression(return_stmt.value) if return_stmt.value else None
        self.push_node(Return(value_var))
