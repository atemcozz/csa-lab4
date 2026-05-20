from __future__ import annotations

import compiler.ast as ast
from compiler.lexer import Token, TokenType


class ParserError(Exception):
    def __init__(self, message: str, faulty_token: Token | None = None):
        super().__init__(message)
        self.faulty_token = faulty_token


INTERNAL_TYPE_KEYWORD = {"int": ast.InternalType.INT, "void": ast.InternalType.VOID}

LOGICAL_OR = TokenType.OP_LOGICAL_OR
LOGICAL_AND = TokenType.OP_LOGICAL_AND
EQUALITY_OPS = {TokenType.OP_EQ, TokenType.OP_NEQ}
RELATIONAL_OPS = {TokenType.OP_LT, TokenType.OP_GT, TokenType.OP_LEQ, TokenType.OP_GEQ}
SHIFT_OPS = {TokenType.OP_LSHIFT, TokenType.OP_RSHIFT}
ADDITIVE_OPS = {TokenType.OP_PLUS, TokenType.OP_MINUS}
MULTIPLICATIVE_OPS = {TokenType.OP_MUL, TokenType.OP_DIV, TokenType.OP_MOD}
BITWISE_OPS = {TokenType.OP_OR, TokenType.OP_XOR, TokenType.OP_AND}


INTERRUPT_KEYWORD = "__interrupt__"


# helper class for decl suffix
class DeclarationSuffix:
    def __init__(self, is_array: bool, array_size: int | None, initializer: ast.Expression | None):
        self.is_array = is_array
        self.array_size = array_size
        self.initializer = initializer


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.position = 0

    def parse(self) -> ast.Program:
        start_token = self.peek_token()
        if not start_token:
            raise ParserError("No tokens to parse")
        token = self.peek_token()
        declarations = []
        while token:
            if token.type == TokenType.EOF:
                break
            decl = self.parse_external_declaration()
            if decl:
                declarations.append(decl)
            else:
                raise ParserError("Unexpected token: " + repr(token), token)
            token = self.peek_token()

        return ast.Program(declarations, start_token)

    def peek_token(self) -> Token | None:
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return None

    def peek_next_token(self) -> Token | None:
        if self.position + 1 < len(self.tokens):
            return self.tokens[self.position + 1]
        return None

    def consume_token(self) -> Token | None:
        if self.position < len(self.tokens):
            token = self.tokens[self.position]
            self.position += 1
            return token
        return None

    def parse_string_literal(self) -> ast.StringLiteral:
        token = self.consume_token()
        if token and token.type == TokenType.STRING_LITERAL and token.value is not None:
            return ast.StringLiteral(token.value, token)
        raise ParserError("Expected string literal", token)

    def parse_char_literal(self) -> ast.CharLiteral:
        token = self.consume_token()
        if token and token.type == TokenType.CHAR_LITERAL and token.value is not None:
            return ast.CharLiteral(token.value, token)
        raise ParserError("Expected char literal", token)

    def parse_number_literal(self) -> ast.IntLiteral:
        token = self.consume_token()
        if token and token.type == TokenType.INT_LITERAL and token.value is not None:
            return ast.IntLiteral(int(token.value), token)
        raise ParserError("Expected number literal", token)

    def parse_identifier(self) -> ast.Identifier:
        token = self.consume_token()
        if token and token.type == TokenType.IDENTIFIER and token.value is not None:
            return ast.Identifier(token.value, token)
        raise ParserError("Expected identifier", token)

    def parse_interrupt_marker(self) -> ast.InterruptMarker:
        interrupt_token = self.consume_token()
        if (
            not interrupt_token
            or interrupt_token.type != TokenType.KEYWORD
            or interrupt_token.value != INTERRUPT_KEYWORD
        ):
            raise ParserError(f"Expected '{INTERRUPT_KEYWORD}'", interrupt_token)

        lparen_token = self.consume_token()

        if not lparen_token or lparen_token.type != TokenType.LPAREN:
            raise ParserError("Expected '('", lparen_token)

        int_token = self.consume_token()

        if not int_token:
            raise ParserError("Unexpected end of input")
        if int_token.type != TokenType.INT_LITERAL or int_token.value is None:
            raise ParserError("Integer literal expected", int_token)

        rparen_token = self.consume_token()
        if not rparen_token or rparen_token.type != TokenType.RPAREN:
            raise ParserError("Expected ')'", rparen_token)

        return ast.InterruptMarker(int(int_token.value), interrupt_token)

    def parse_parameter(self) -> ast.Parameter:
        s = self.parse_type_specifier()

        identifier_token = self.consume_token()
        if not identifier_token or identifier_token.type != TokenType.IDENTIFIER or identifier_token.value is None:
            raise ParserError("Expected parameter identifier", identifier_token)

        is_array = False
        lbracket_token = self.peek_token()
        if lbracket_token and lbracket_token.type == TokenType.LBRACKET:
            is_array = True
            self.consume_token()  # consume '['
            rbracket_token = self.consume_token()
            if not rbracket_token or rbracket_token.type != TokenType.RBRACKET:
                raise ParserError("Expected ']'", rbracket_token)

        return ast.Parameter(s, identifier_token.value, is_array, identifier_token)

    def parse_parameter_list(self) -> list[ast.Parameter]:
        params = []

        while True:
            param = self.parse_parameter()
            params.append(param)

            comma_token = self.peek_token()

            if comma_token and comma_token.type == TokenType.COMMA:
                self.consume_token()

            elif comma_token and comma_token.type == TokenType.RPAREN:
                break
            else:
                raise ParserError("Expected ',' or ')'", comma_token)

        return params

    def parse_type_specifier(self) -> ast.InternalType | ast.Identifier:
        token = self.consume_token()
        if token and token.type == TokenType.KEYWORD and token.value is not None:
            if token.value in INTERNAL_TYPE_KEYWORD:
                return ast.InternalType(token.value)
            raise ParserError(f"Invalid type identifier: {token.value}", token)
        if token and token.type == TokenType.IDENTIFIER and token.value is not None:
            return ast.Identifier(token.value, token)
        raise ParserError("Expected type identifier", token)

    def parse_function_suffix(self) -> tuple[list[ast.Parameter], ast.CompoundStatement]:
        lparen_token = self.consume_token()
        if not lparen_token or lparen_token.type != TokenType.LPAREN:
            raise ParserError("Expected '('", lparen_token)

        params = []
        param_token = self.peek_token()

        if not param_token:
            raise ParserError("Unexpected end of input")

        if param_token.type != TokenType.RPAREN:
            params = self.parse_parameter_list()

        rparen_token = self.consume_token()
        if not rparen_token or rparen_token.type != TokenType.RPAREN:
            raise ParserError("Expected ')' after parameter list", rparen_token)

        body = self.parse_compound_statement()
        return params, body

    def parse_semicolon(self):
        semicolon_token = self.consume_token()
        if not semicolon_token or semicolon_token.type != TokenType.SEMICOLON:
            raise ParserError("Expected ';'", semicolon_token)

    def parse_array_declaration_suffix(self, next_token) -> DeclarationSuffix:
        if next_token.type == TokenType.INT_LITERAL:
            if next_token.value is None:
                raise ParserError("Expected array size", next_token)
            rbracket_token = self.consume_token()
            if not rbracket_token or rbracket_token.type != TokenType.RBRACKET:
                raise ParserError("Expected ']'", rbracket_token)
            self.parse_semicolon()
            return DeclarationSuffix(is_array=True, array_size=int(next_token.value), initializer=None)

        if next_token.type == TokenType.RBRACKET:
            assign_token = self.consume_token()
            if not assign_token or assign_token.type != TokenType.OP_ASSIGN:
                raise ParserError("Expected '='", assign_token)
            res = self.parse_string_literal()
            self.parse_semicolon()
            return DeclarationSuffix(is_array=True, array_size=None, initializer=res)

        raise ParserError("Expected initializer or array size", next_token)

    def parse_declaration_suffix(self) -> DeclarationSuffix:
        token = self.consume_token()

        if not token:
            raise ParserError("Unexpected end of input", token)

        if token.type == TokenType.OP_ASSIGN:
            res = self.parse_expression()
            self.parse_semicolon()
            return DeclarationSuffix(is_array=False, array_size=None, initializer=res)

        next_token = self.consume_token()

        if not next_token:
            raise ParserError("Unexpected end of input", token)

        if token.type == TokenType.LBRACKET:
            return self.parse_array_declaration_suffix(next_token)

        raise ParserError("Expected initializer or array size", token)

    def parse_keyword_statement(self, token) -> ast.Statement:
        if token.value == "if":
            return self.parse_if_statement()
        if token.value == "while":
            return self.parse_while_statement()
        if token.value == "return":
            return self.parse_return_statement()
        raise ParserError(f"Unexpected keyword {token.value}")

    def parse_statement(self) -> ast.Statement:
        token = self.peek_token()
        if not token:
            raise ParserError("Unexpected end of input")

        if token.type == TokenType.KEYWORD:
            return self.parse_keyword_statement(token)

        if token.type == TokenType.LBRACE:
            return self.parse_compound_statement()

        old_pos = self.position
        try:
            return self.parse_assign_statement()
        except ParserError:
            self.position = old_pos
            return self.parse_expression_statement()

    def parse_expression(self) -> ast.Expression:
        return self.parse_logical_or_expression()

    def parse_expression_statement(self) -> ast.ExpressionStatement:
        token = self.peek_token()
        if token and token.type == TokenType.SEMICOLON:
            self.consume_token()
            return ast.ExpressionStatement(token)
        expr = self.parse_expression()
        self.parse_semicolon()
        return ast.ExpressionStatement(expr.start_token, expr)

    def parse_logical_or_expression(self) -> ast.Expression:
        left = self.parse_logical_and_expression()
        logical_or_token = self.peek_token()
        while logical_or_token and logical_or_token.type == TokenType.OP_LOGICAL_OR:
            self.consume_token()
            right = self.parse_logical_and_expression()
            if not logical_or_token.value:
                raise ParserError("Expected ||", logical_or_token)
            left = ast.BinaryExpression(logical_or_token, left, right, left.start_token)
            logical_or_token = self.peek_token()

        return left

    def parse_logical_and_expression(self) -> ast.Expression:
        left = self.parse_equality_expression()
        logical_and_token = self.peek_token()
        while logical_and_token and logical_and_token.type == TokenType.OP_LOGICAL_AND:
            self.consume_token()
            right = self.parse_equality_expression()
            if not logical_and_token.value:
                raise ParserError("Expected &&", logical_and_token)
            left = ast.BinaryExpression(logical_and_token, left, right, left.start_token)
            logical_and_token = self.peek_token()

        return left

    def parse_equality_expression(self) -> ast.Expression:
        left = self.parse_relational_expression()
        equality_token = self.peek_token()
        while equality_token and equality_token.type in EQUALITY_OPS:
            self.consume_token()
            right = self.parse_relational_expression()
            left = ast.BinaryExpression(equality_token, left, right, left.start_token)
            equality_token = self.peek_token()
        return left

    def parse_relational_expression(self) -> ast.Expression:
        left = self.parse_shift_expression()
        relational_token = self.peek_token()
        while relational_token and relational_token.type in RELATIONAL_OPS:
            self.consume_token()
            right = self.parse_shift_expression()
            left = ast.BinaryExpression(relational_token, left, right, left.start_token)
            relational_token = self.peek_token()
        return left

    def parse_shift_expression(self) -> ast.Expression:
        left = self.parse_additive_expression()
        shift_token = self.peek_token()
        while shift_token and shift_token.type in SHIFT_OPS:
            self.consume_token()
            right = self.parse_additive_expression()
            left = ast.BinaryExpression(shift_token, left, right, left.start_token)
            shift_token = self.peek_token()
        return left

    def parse_additive_expression(self) -> ast.Expression:
        left = self.parse_multiplicative_expression()
        additive_token = self.peek_token()
        while additive_token and additive_token.type in ADDITIVE_OPS:
            self.consume_token()
            right = self.parse_multiplicative_expression()
            left = ast.BinaryExpression(additive_token, left, right, left.start_token)
            additive_token = self.peek_token()
        return left

    def parse_multiplicative_expression(self) -> ast.Expression:
        left = self.parse_bitwise_expression()
        multiplicative_token = self.peek_token()
        while multiplicative_token and multiplicative_token.type in MULTIPLICATIVE_OPS:
            self.consume_token()
            right = self.parse_bitwise_expression()
            left = ast.BinaryExpression(multiplicative_token, left, right, left.start_token)
            multiplicative_token = self.peek_token()
        return left

    def parse_bitwise_expression(self) -> ast.Expression:
        left = self.parse_unary_expression()
        bitwise_token = self.peek_token()
        while bitwise_token and bitwise_token.type in BITWISE_OPS:
            self.consume_token()
            right = self.parse_unary_expression()
            left = ast.BinaryExpression(bitwise_token, left, right, left.start_token)
            bitwise_token = self.peek_token()
        return left

    def parse_unary_expression(self) -> ast.Expression:
        token = self.peek_token()
        if token and (
            token.type == TokenType.OP_MINUS or token.type == TokenType.OP_LOGICAL_NOT or token.type == TokenType.OP_NOT
        ):
            token = self.consume_token()
            if not token:
                raise ParserError("Unexpected end of input")
            operand = self.parse_unary_expression()
            return ast.UnaryExpression(token, operand, token)
        return self.parse_primary_expression()

    def parse_argument_expression_list(self) -> list[ast.Expression]:
        args = []
        token = self.peek_token()
        if token and token.type == TokenType.RPAREN:
            return args

        while True:
            expression = self.parse_expression()
            args.append(expression)
            comma_token = self.peek_token()
            if comma_token and comma_token.type == TokenType.COMMA:
                self.consume_token()
            else:
                break
        return args

    def parse_identifier_expression(self, ident: ast.Identifier) -> ast.Expression:
        next_token = self.peek_token()
        if next_token and next_token.type == TokenType.LBRACKET:
            lbracket = self.consume_token()  # '['
            expr = self.parse_expression()
            rbracket = self.consume_token()
            if not rbracket or rbracket.type != TokenType.RBRACKET:
                raise ParserError("Expected ']'", lbracket)
            return ast.IndexExpression(ident.name, expr, rbracket)
        if next_token and next_token.type == TokenType.LPAREN:
            lparen = self.consume_token()  # '('
            if not lparen:
                raise ParserError("Unexpected end of input")
            args = self.parse_argument_expression_list()
            rparen = self.consume_token()
            if not rparen or rparen.type != TokenType.RPAREN:
                raise ParserError("Expected ')'", rparen)
            return ast.CallExpression(ident.name, args, lparen)
        return ident

    def parse_paren_expression(self) -> ast.Expression:
        self.consume_token()
        expr = self.parse_expression()
        rparen = self.consume_token()
        if not rparen or rparen.type != TokenType.RPAREN:
            raise ParserError("Expected ')'", rparen)
        return expr

    def parse_primary_expression(self) -> ast.Expression:
        token = self.peek_token()
        if not token:
            raise ParserError("Unexpected end of input")

        if token.type == TokenType.IDENTIFIER:
            ident = self.parse_identifier()
            return self.parse_identifier_expression(ident)

        if token.type == TokenType.INT_LITERAL:
            return self.parse_number_literal()

        if token.type == TokenType.CHAR_LITERAL:
            return self.parse_char_literal()

        if token.type == TokenType.STRING_LITERAL:
            return self.parse_string_literal()

        if token.type == TokenType.LPAREN:
            return self.parse_paren_expression()

        raise ParserError("Expected primary expression", token)

    def parse_external_declaration(self) -> ast.Declaration | None:
        token = self.peek_token()
        if not token:
            return None

        if token.type == TokenType.KEYWORD and token.value == INTERRUPT_KEYWORD:
            interrupt_marker = self.parse_interrupt_marker()
            type_specifier = self.parse_type_specifier()
            identifier = self.parse_identifier()
            params, body = self.parse_function_suffix()
            return ast.FunctionDefinition(type_specifier, identifier.name, params, body, token, interrupt_marker)
        if (token.type == TokenType.KEYWORD and token.value in INTERNAL_TYPE_KEYWORD) or (
            token.type == TokenType.IDENTIFIER
        ):
            type_specifier = self.parse_type_specifier()
            identifier = self.parse_identifier()
            next_token = self.peek_token()
            if next_token and next_token.type == TokenType.LPAREN:
                params, body = self.parse_function_suffix()
                return ast.FunctionDefinition(type_specifier, identifier.name, params, body, token)
            if next_token and (next_token.type == TokenType.OP_ASSIGN or next_token.type == TokenType.LBRACKET):
                decl_suffix = self.parse_declaration_suffix()
                return ast.VariableDeclaration(
                    type_specifier,
                    decl_suffix.is_array,
                    identifier.name,
                    token,
                    decl_suffix.initializer,
                    decl_suffix.array_size,
                )
        return None

    def is_declaration(self, token: Token) -> bool:
        if token.type == TokenType.KEYWORD and token.value in INTERNAL_TYPE_KEYWORD:
            return True
        if token.type == TokenType.IDENTIFIER:
            next_token = self.peek_next_token()
            if next_token and next_token.type == TokenType.IDENTIFIER:
                return True
        return False

    def parse_compound_item(self) -> ast.ASTNode:
        token = self.peek_token()
        if token and self.is_declaration(token):
            item = self.parse_external_declaration()
            if not item:
                raise ParserError("Invalid declaration", token)
            return item
        item = self.parse_statement()
        if not item:
            raise ParserError("Invalid statement", token)
        return item

    def parse_compound_statement(self) -> ast.CompoundStatement:
        lbrace_token = self.consume_token()
        if not lbrace_token or lbrace_token.type != TokenType.LBRACE:
            raise ParserError("Expected '{'", lbrace_token)
        items = []
        while True:
            token = self.peek_token()
            if not token:
                raise ParserError("Unexpected end of input")
            if token.type == TokenType.RBRACE:
                self.consume_token()
                break
            items.append(self.parse_compound_item())
        return ast.CompoundStatement(items, lbrace_token)

    def parse_assign_statement(self) -> ast.AssignStatement:
        identifier = self.parse_identifier()
        token = self.consume_token()
        if token and token.type == TokenType.OP_ASSIGN:
            expression = self.parse_expression()
            self.parse_semicolon()
            return ast.AssignStatement(identifier, expression, identifier.start_token)

        if token and token.type == TokenType.LBRACKET:
            expression = self.parse_expression()
            rbracket_token = self.consume_token()
            if not rbracket_token or rbracket_token.type != TokenType.RBRACKET:
                raise ParserError("Expected ']'", rbracket_token)
            assign_token = self.consume_token()
            if not assign_token or assign_token.type != TokenType.OP_ASSIGN:
                raise ParserError("Expected '='", assign_token)
            value_expression = self.parse_expression()
            self.parse_semicolon()
            index_expr = ast.IndexExpression(identifier.name, expression, token)
            return ast.AssignStatement(index_expr, value_expression, identifier.start_token)
        raise ParserError("Expected assignment statement", token)

    def parse_if_statement(self) -> ast.IfStatement:
        if_token = self.consume_token()
        if not if_token or if_token.type != TokenType.KEYWORD or if_token.value != "if":
            raise ParserError("Expected 'if'", if_token)

        lparen_token = self.consume_token()
        if not lparen_token or lparen_token.type != TokenType.LPAREN:
            raise ParserError("Expected '('", lparen_token)

        condition = self.parse_expression()

        rparen_token = self.consume_token()
        if not rparen_token or rparen_token.type != TokenType.RPAREN:
            raise ParserError("Expected ')'", rparen_token)

        then_branch = self.parse_statement()

        else_branch = None
        next_token = self.peek_token()
        if next_token and next_token.type == TokenType.KEYWORD and next_token.value == "else":
            self.consume_token()
            else_branch = self.parse_statement()

        return ast.IfStatement(condition, then_branch, if_token, else_branch)

    def parse_while_statement(self) -> ast.WhileStatement:
        while_token = self.consume_token()
        if not while_token or while_token.type != TokenType.KEYWORD or while_token.value != "while":
            raise ParserError("Expected 'while'", while_token)

        lparen_token = self.consume_token()
        if not lparen_token or lparen_token.type != TokenType.LPAREN:
            raise ParserError("Expected '('", lparen_token)

        condition = self.parse_expression()

        rparen_token = self.consume_token()
        if not rparen_token or rparen_token.type != TokenType.RPAREN:
            raise ParserError("Expected ')'", rparen_token)

        body = self.parse_statement()

        return ast.WhileStatement(condition, body, while_token)

    def parse_return_statement(self) -> ast.ReturnStatement:
        return_token = self.consume_token()
        if not return_token or return_token.type != TokenType.KEYWORD or return_token.value != "return":
            raise ParserError("Expected 'return'", return_token)

        next_token = self.peek_token()
        if next_token and next_token.type == TokenType.SEMICOLON:
            self.consume_token()
            return ast.ReturnStatement(return_token)
        value = self.parse_expression()
        self.parse_semicolon()
        return ast.ReturnStatement(return_token, value)
