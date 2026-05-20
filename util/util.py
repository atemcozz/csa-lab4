
import compiler.ast as ast


def sign_extend(value, bits):
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)


def visualize_ast_field(key, value, indent) -> str:
    ind = "  " * indent
    if isinstance(value, list):
        if not value:
            return f"{ind}  {key}: []\n"
        result = f"{ind}  {key}:\n"
        for item in value:
            result += visualize_ast_program_tree(item, indent + 2)
        return result
    if isinstance(value, ast.ASTNode):
        return f"{ind}  {key}:\n" + visualize_ast_program_tree(value, indent + 2)
    if isinstance(value, (ast.InternalType, ast.Identifier)):
        return f"{ind}  {key}: {value}\n"
    return f"{ind}  {key}: {value!r}\n"


def visualize_ast_program_tree(node: ast.ASTNode, indent=0) -> str:
    result = ""
    ind = "  " * indent

    if isinstance(
        node, (ast.Identifier, ast.Parameter, ast.IntLiteral, ast.CharLiteral, ast.StringLiteral, ast.InterruptMarker)
    ):
        return f"{ind}{node!r}\n"

    result += f"{ind}{node.__class__.__name__}:\n"

    for key, value in vars(node).items():
        if value is None:
            continue
        result += visualize_ast_field(key, value, indent)
    return result
