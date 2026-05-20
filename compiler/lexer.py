from __future__ import annotations

from enum import Enum


class LexerError(Exception):
    pass


class TokenType(Enum):
    IDENTIFIER = 1
    KEYWORD = 2
    INT_LITERAL = 4
    STRING_LITERAL = 5
    CHAR_LITERAL = 6
    LPAREN = 7
    RPAREN = 8
    LBRACE = 9
    RBRACE = 10
    LBRACKET = 11
    RBRACKET = 12
    EOF = 13
    OP_PLUS = 14
    OP_MINUS = 15
    OP_MUL = 16
    OP_DIV = 17
    OP_ASSIGN = 18
    OP_EQ = 19
    OP_NEQ = 20
    OP_LT = 21
    OP_GT = 22
    OP_LEQ = 23
    OP_GEQ = 24
    OP_MOD = 25
    OP_LOGICAL_NOT = 26
    OP_LOGICAL_AND = 27
    OP_LOGICAL_OR = 28
    OP_AND = 29
    OP_OR = 30
    OP_XOR = 31
    SEMICOLON = 32
    COMMA = 33
    OP_LSHIFT = 34
    OP_RSHIFT = 35
    OP_NOT = 36


KEYWORD = {"int", "if", "else", "while", "return", "void", "__interrupt__"}


OPERATOR_TOKENS = {
    "+": TokenType.OP_PLUS,
    "-": TokenType.OP_MINUS,
    "*": TokenType.OP_MUL,
    "/": TokenType.OP_DIV,
    "=": TokenType.OP_ASSIGN,
    "==": TokenType.OP_EQ,
    "!=": TokenType.OP_NEQ,
    "<": TokenType.OP_LT,
    ">": TokenType.OP_GT,
    "<=": TokenType.OP_LEQ,
    ">=": TokenType.OP_GEQ,
    "%": TokenType.OP_MOD,
    "!": TokenType.OP_LOGICAL_NOT,
    "&&": TokenType.OP_LOGICAL_AND,
    "||": TokenType.OP_LOGICAL_OR,
    "&": TokenType.OP_AND,
    "|": TokenType.OP_OR,
    "^": TokenType.OP_XOR,
    "<<": TokenType.OP_LSHIFT,
    ">>": TokenType.OP_RSHIFT,
    "~": TokenType.OP_NOT,
}

BRACE_TOKENS = {
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
}


class Token:
    def __init__(self, token_type: TokenType, value: str | None, source_line: int, source_column: int):
        self.type = token_type
        self.value = value
        self.source_line = source_line
        self.source_column = source_column

    def __repr__(self):
        return f"Token({self.type}, {self.value}, line={self.source_line}, column={self.source_column})"


class Lexer:
    def __init__(self, input_string):
        self.input_string = input_string
        self.position = 0
        self.line_number = 1
        self.last_line_start = 0

    def is_ascii(self, char: str) -> bool:
        return ord(char) < 128

    def has_more_tokens(self):
        return self.position < len(self.input_string)

    def consume_char(self) -> str | None:
        if self.has_more_tokens():
            token = self.input_string[self.position]
            self.move_next()
            return token
        return None

    def peek_char(self) -> str | None:
        if self.has_more_tokens():
            return self.input_string[self.position]
        return None

    def peek_next_char(self) -> str | None:
        if self.position + 1 < len(self.input_string):
            return self.input_string[self.position + 1]
        return None

    def move_next(self):
        if self.has_more_tokens():
            self.position += 1

    def read_number(self) -> Token | None:
        num_str = ""
        while self.has_more_tokens():
            char = self.peek_char()
            if char is None:
                break
            if char.isdigit():
                num_str += char
                self.consume_char()

            elif char.isalpha() or char == "_":
                raise LexerError(f"Unexpected symbol: '{char}'")
            else:
                break

        if num_str == "":
            raise LexerError("Expected number literal")
        return Token(TokenType.INT_LITERAL, num_str, self.line_number, self.position - self.last_line_start)

    def skip_blanks_and_comments(self):
        while self.has_more_tokens():
            char = self.peek_char()
            if char is not None and char.isspace():
                if char == "\n":
                    self.line_number += 1
                    self.last_line_start = self.position + 1
                self.consume_char()
            elif char == "/" and self.peek_next_char() == "/":
                self.consume_char()
                self.consume_char()
                while self.has_more_tokens():
                    char = self.consume_char()
                    if char == "\n":
                        self.line_number += 1
                        self.last_line_start = self.position
                        break
            else:
                break

    def read_brace(self) -> Token | None:
        char = self.consume_char()
        if char is None:
            raise LexerError("Unexpected end of input")
        if char in BRACE_TOKENS:
            return Token(BRACE_TOKENS[char], char, self.line_number, self.position - self.last_line_start)
        raise LexerError(f"Unexpected symbol: '{char}'")

    def read_identifier_or_keyword(self) -> Token:
        char = self.consume_char()
        if char is None:
            raise LexerError("Unexpected end of input")

        if not (char.isalpha() or char == "_"):
            raise LexerError(f"Unexpected symbol: '{char}'")
        word_str = char

        while self.has_more_tokens():
            char = self.peek_char()
            if char is not None and (char.isalnum() or char == "_"):
                word_str += char
                self.consume_char()
            else:
                break
        if word_str in KEYWORD:
            return Token(TokenType.KEYWORD, word_str, self.line_number, self.position - self.last_line_start)
        return Token(TokenType.IDENTIFIER, word_str, self.line_number, self.position - self.last_line_start)

    def process_escape_char(self, char: str) -> str:
        match char:
            case "n":
                return "\n"
            case "0":
                return "\0"
            case "t":
                return "\t"
            case "'":
                return "'"
            case '"':
                return '"'
            case "\\":
                return "\\"
            case _:
                raise LexerError(f"Unexpected escape: \\{char}")

    def read_char_literal(self) -> Token:
        char_literal = ""

        quot = self.consume_char()
        if quot is None or quot != "'":
            raise LexerError("Expected '''")

        char = self.consume_char()
        if char is None:
            raise LexerError("Expected character literal")

        if char == "\\":
            next_char = self.consume_char()
            if next_char is None:
                raise LexerError("Unterminated char literal")

            char_literal = self.process_escape_char(next_char)

        elif char == "'":
            raise LexerError("Char literal cannot be empty")
        else:
            char_literal = char

        next_char = self.peek_char()
        if next_char != "'":
            raise LexerError("Char literal must be a single character")

        self.consume_char()
        return Token(TokenType.CHAR_LITERAL, char_literal, self.line_number, self.position - self.last_line_start)

    def read_string_literal(self) -> Token:
        quot = self.consume_char()
        if quot != '"':
            raise LexerError('Expected "')

        string_literal = ""
        while self.has_more_tokens():
            char = self.consume_char()
            if char in ("\n", None):
                raise LexerError("Unterminated string literal")

            if char == '"':
                return Token(
                    TokenType.STRING_LITERAL, string_literal, self.line_number, self.position - self.last_line_start
                )

            if char == "\\":
                next_char = self.consume_char()
                if next_char is None:
                    raise LexerError("Unterminated string literal")
                string_literal += self.process_escape_char(next_char)
            else:
                string_literal += char

        raise LexerError("Unexpected end of string literal")

    def read_operator(self) -> Token | None:
        char = self.consume_char()
        if char is None:
            raise LexerError("Unexpected end of input")
        next_char = self.peek_char()

        if next_char is not None and char + next_char in OPERATOR_TOKENS:
            self.consume_char()
            return Token(
                OPERATOR_TOKENS[char + next_char],
                char + next_char,
                self.line_number,
                self.position - self.last_line_start,
            )

        if char in OPERATOR_TOKENS:
            return Token(OPERATOR_TOKENS[char], char, self.line_number, self.position - self.last_line_start)
        raise LexerError(f"Unexpected operator: '{char}'")

    def _read_next_token(self, char: str) -> Token | None:
        if char.isdigit():
            return self.read_number()
        if char.isalpha() or char == "_":
            return self.read_identifier_or_keyword()

        single_char_tokens = {";": TokenType.SEMICOLON, ",": TokenType.COMMA}
        if char in single_char_tokens:
            self.consume_char()
            return Token(single_char_tokens[char], char, self.line_number, self.position - self.last_line_start)

        handlers = {"'": self.read_char_literal, '"': self.read_string_literal}
        if char in handlers:
            return handlers[char]()

        if char in BRACE_TOKENS:
            return self.read_brace()
        if char in OPERATOR_TOKENS:
            return self.read_operator()

        raise LexerError(f"Unexpected symbol: '{char}'")

    def tokenize(self):
        tokens = []

        while self.has_more_tokens():
            self.skip_blanks_and_comments()
            if not self.has_more_tokens():
                break

            char = self.peek_char()
            if char is None:
                raise LexerError("Unexpected end of input")

            tokens.append(self._read_next_token(char))
        tokens.append(Token(TokenType.EOF, None, self.line_number, self.position - self.last_line_start))

        return tokens
