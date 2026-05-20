from __future__ import annotations

import logging

from machine import isa
from util.util import visualize_ast_program_tree

import compiler.ast as ast
from compiler import ir
from compiler.backend import BackendError, CompilerBackend
from compiler.ir import IRGenerationError, IRGenerator
from compiler.lexer import Lexer, LexerError
from compiler.parser import Parser, ParserError
from compiler.semantic_analyzer import SemanticAnalyzer, SemanticError


def generate_line_error_msg(line: str, row: int, col: int):
    return f"At line {row}, column {col}:\n{line}\n{' ' * (col - 1)}^"


def process_tokenize(tokenizer: Lexer, lines: list[str], verbose = False):
    logger = logging.getLogger(__name__)
    tokens = []
    try:
        tokens = tokenizer.tokenize()
        if verbose:
            logger.debug("Lexer output:")
            for token in tokens:
                logger.debug(token)

    except LexerError:
        column_number = tokenizer.position - tokenizer.last_line_start
        line_msg = generate_line_error_msg(lines[tokenizer.line_number - 1], tokenizer.line_number, column_number)
        logger.exception(line_msg)
        logger.exception("Lexer error")
        return None
    return tokens


def process_parse(parser: Parser, tokens: list[ast.Token], lines: list[str], verbose=False):
    logger = logging.getLogger(__name__)
    ast_tree = ast.Program([], tokens[0])
    try:
        ast_tree = parser.parse()
        if verbose:
            ast_string = visualize_ast_program_tree(ast_tree)
            logger.debug("Parsed AST:")
            logger.debug(ast_string)
    except ParserError as e:
        token = e.faulty_token
        if token:
            line_msg = generate_line_error_msg(lines[token.source_line - 1], token.source_line, token.source_column)
            logger.exception(line_msg)
        logger.exception("Parser error")
        return None
    return ast_tree

def process_analyze(semantic_analyzer: SemanticAnalyzer, ast_tree: ast.Program, lines: list[str]):
    logger = logging.getLogger(__name__)
    try:
        semantic_analyzer.analyze_tree(ast_tree)
    except SemanticError as e:
        if e.faulty_ast_node:
            node = e.faulty_ast_node
            token = node.start_token
            if token:
                line_msg = generate_line_error_msg(lines[token.source_line - 1], token.source_line, token.source_column)
                logger.exception(line_msg)
        logger.exception("Semantic error")
        return False
    return True


def process_generate_ir(ir_generator: IRGenerator, ast_tree: ast.Program, lines: list[str], verbose=False):
    logger = logging.getLogger(__name__)
    ir = None
    try:
        ir = ir_generator.generate_from_ast(ast_tree, entry_point="function_main")
        if verbose:
            logger.debug("Generated IR:")
            for node in ir_generator.instructions:
                logger.debug(f"  {node}")

            logger.debug("Data section:")
            for node in ir_generator.data:
                logger.debug(f"  {node}")

    except IRGenerationError as e:
        if not e.faulty_ast_node:
            logger.exception("IR generation error")
            return None
        node = e.faulty_ast_node
        token = node.start_token
        if token:
            line_msg = generate_line_error_msg(lines[token.source_line - 1], token.source_line, token.source_column)
            logger.exception(line_msg)
        logger.exception("IR generation error")
        return None
    return ir

def process_compile_backend(ir: ir.Program, lines: list[str], verbose=False):
    logger = logging.getLogger(__name__)
    try:
        backend = CompilerBackend(ir)
        machine_code, defs = backend.compile_binary()
        if verbose:
            logger.debug("Compiled machine code:")
            for i in range(0, len(machine_code), 4):
                word = machine_code[i : i + 4]
                word_int = int.from_bytes(word, byteorder="little")
                try:
                    mnemonic = isa.parse_instr_mnemonic(word_int)
                except ValueError:
                    mnemonic = "?"
                logger.debug(f"0x{i:04x}: {' '.join(f'{j:02x}' for j in word)} | {mnemonic}")
            logger.debug("Definitions:")
            for name, offset in defs.items():
                logger.debug(f"  {name}: {offset}")
    except BackendError:
        logger.exception("Backend error")
        return None
    return machine_code, defs

def compile_program_pipeline(input_content: str, verbose: bool):
    lines = input_content.splitlines()
    # lexer
    tokens = process_tokenize(Lexer(input_content), lines, verbose=verbose)
    if tokens is None:
        return None
    # parser
    ast_tree = process_parse(Parser(tokens), tokens, lines, verbose=verbose)
    if ast_tree is None:
        return None

    # semantic analyzer
    if not process_analyze(SemanticAnalyzer(), ast_tree, lines):
        return None
    # ir
    ir = process_generate_ir(IRGenerator(), ast_tree, lines, verbose=verbose)
    if ir is None:
        return None
    # backend
    return process_compile_backend(ir, lines, verbose=verbose)


def compile_program(input_path: str, output_path: str, output_hex_path: str | None = None, verbose=False):
    input_content = ""
    with open(input_path) as f:
        input_content = f.read()

    backend_res = compile_program_pipeline(input_content, verbose=verbose)
    if backend_res is None:
        return

    machine_code, _defs = backend_res

    with open(output_path, "wb") as f:
        f.write(machine_code)

    if output_hex_path:
        with open(output_hex_path, "w") as f:
            for i in range(0, len(machine_code), 4):
                word = machine_code[i : i + 4]
                word_int = int.from_bytes(word, byteorder="little")
                mnemonic = isa.parse_instr_mnemonic(word_int)
                f.write(f"{i} - {word_int:08x} - {mnemonic}\n")
    print(f"source LoC: {len(input_content.splitlines())}, code instr: {len(machine_code) // 4}")
