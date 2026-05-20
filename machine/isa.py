from __future__ import annotations

from enum import Enum

from util.util import sign_extend

REGISTERS_COUNT = 32

IO_INPUT_PORTS_COUNT = 4
IO_OUTPUT_PORTS_COUNT = 4

WORD_SIZE = 4
WORD_MASK = 0xFFFFFFFF


class Regs(Enum):
    zero = 0
    ra = 1
    sp = 2
    gp = 3
    tp = 4
    t0 = 5
    t1 = 6
    t2 = 7
    s0 = 8
    fp = 8
    s1 = 9
    a0 = 10
    a1 = 11
    a2 = 12
    a3 = 13
    a4 = 14
    a5 = 15
    a6 = 16
    a7 = 17
    s2 = 18
    s3 = 19
    s4 = 20
    s5 = 21
    s6 = 22
    s7 = 23
    s8 = 24
    s9 = 25
    s10 = 26
    s11 = 27
    t3 = 28
    t4 = 29
    t5 = 30
    t6 = 31


REGS_NAMES = [Regs(i).name for i in range(32)]


INT_TABLE_BASE = 0x10


class CUState(Enum):
    FETCH = 0
    DECODE = 1
    EXECUTE = 2
    MEMORY = 3
    WRITEBACK = 4
    TRAP = 5
    TRAP_MEMORY = 6
    TRAP_WRITEBACK = 7


class OpCode(Enum):
    # arithmetic
    ADD = 0x00
    NOT = 0x01
    ADDI = 0x02
    SUB = 0x03
    MUL = 0x04
    DIV = 0x05
    AND = 0x06
    OR = 0x07
    XOR = 0x08
    REM = 0x09
    # shifts
    SLL = 0x0A
    SRL = 0x0B
    SRA = 0x0C
    SLLI = 0x0D

    # memory
    LW = 0x10
    SW = 0x11
    LUI = 0x12

    # control flow
    JAL = 0x21
    JALR = 0x22
    BEQ = 0x23
    BNE = 0x24
    BLT = 0x25
    BGE = 0x26

    # i/o

    IN = 0x30
    OUT = 0x31

    # trap
    EI = 0x32
    DI = 0x33
    IRET = 0x34

    HALT = 0x3F


OPCODE_VALUES = {op.value: op for op in OpCode}

# rd, rs1, rs2
R_OPCODES = {
    OpCode.ADD,
    OpCode.SUB,
    OpCode.MUL,
    OpCode.DIV,
    OpCode.AND,
    OpCode.OR,
    OpCode.XOR,
    OpCode.SLL,
    OpCode.SRL,
    OpCode.SRA,
    OpCode.IN,
    OpCode.REM,
    OpCode.NOT,
}

# rd, rs1, imm
I_OPCODES = {OpCode.ADDI, OpCode.LW, OpCode.JALR, OpCode.SLLI}

# rs1, rs2, imm
S_OPCODES = {OpCode.SW, OpCode.OUT}

# rs1, rs2, imm
B_OPCODES = {OpCode.BEQ, OpCode.BNE, OpCode.BLT, OpCode.BGE}

# rd, imm
J_OPCODES = {OpCode.JAL}

# rd, imm
U_OPCODES = {OpCode.LUI}

# imm
SYS_OPCODES = {OpCode.IRET, OpCode.EI, OpCode.DI, OpCode.HALT}


def parse_instr_mnemonic(ins: int):
    opcode_bits = (ins >> 26) & 0x3F
    opcode = OPCODE_VALUES.get(opcode_bits, None)
    if opcode is None:
        return "?"

    rd_idx = (ins >> 21) & 0x1F
    rs1_idx = (ins >> 16) & 0x1F
    rs2_idx = (ins >> 11) & 0x1F

    if opcode in B_OPCODES:
        rd_idx = 0
        rs1_idx = (ins >> 21) & 0x1F
        rs2_idx = (ins >> 16) & 0x1F
    elif opcode in S_OPCODES:
        rd_idx = 0
        rs2_idx = (ins >> 21) & 0x1F
        rs1_idx = (ins >> 16) & 0x1F

    imm_bits = ins & 0xFFFF

    imm = sign_extend(imm_bits, 16)
    j_imm = sign_extend(ins & 0x1FFFFF, 21)

    name = opcode.name.lower()
    args = ""

    reg_rd = REGS_NAMES[rd_idx] if rd_idx < 32 else "?"
    reg_rs1 = REGS_NAMES[rs1_idx] if rs1_idx < 32 else "?"
    reg_rs2 = REGS_NAMES[rs2_idx] if rs2_idx < 32 else "?"
    match opcode:
        case (
            OpCode.ADD
            | OpCode.SUB
            | OpCode.MUL
            | OpCode.DIV
            | OpCode.AND
            | OpCode.OR
            | OpCode.XOR
            | OpCode.SLL
            | OpCode.SRL
            | OpCode.SRA
            | OpCode.REM
        ):
            args = f"{reg_rd}, {reg_rs1}, {reg_rs2}"

        case OpCode.IN | OpCode.NOT:
            args = f"{reg_rd}, {reg_rs1}"

        case OpCode.OUT:
            args = f"{reg_rs1}, {reg_rs2}"

        case OpCode.ADDI | OpCode.LW | OpCode.JALR | OpCode.SLLI:
            args = f"{reg_rd}, {reg_rs1}, {imm}"
        case OpCode.SW:
            args = f"{reg_rs2},  {imm}({reg_rs1})"
        case OpCode.BEQ | OpCode.BNE | OpCode.BLT | OpCode.BGE:
            args = f"{reg_rs1}, {reg_rs2}, {imm}"
        case OpCode.JAL:
            args = f"{reg_rd}, {j_imm}"
        case OpCode.EI | OpCode.DI | OpCode.IRET | OpCode.HALT:
            args = ""
        case OpCode.LUI:
            args = f"{reg_rd}, {imm}"
        case _:
            raise ValueError(f"Unimplemented opcode: {opcode}")
    return f"{name} {args}"


def get_ins_bytes(instruction: int) -> bytes:
    return (instruction & WORD_MASK).to_bytes(WORD_SIZE, "little")


def ins_r(opcode: OpCode, rd: int, rs1: int, rs2: int) -> bytes:
    res = (opcode.value & 0x3F) << 26
    res |= (rd & 0x1F) << 21
    res |= (rs1 & 0x1F) << 16
    res |= (rs2 & 0x1F) << 11
    return get_ins_bytes(res)


def ins_i(opcode: OpCode, rd: int, rs1: int, imm: int) -> bytes:
    res = (opcode.value & 0x3F) << 26
    res |= (rd & 0x1F) << 21
    res |= (rs1 & 0x1F) << 16
    res |= imm & 0xFFFF
    return get_ins_bytes(res)


def ins_b(opcode: OpCode, rs1: int, rs2: int, imm: int) -> bytes:
    res = (opcode.value & 0x3F) << 26
    res |= (rs1 & 0x1F) << 21
    res |= (rs2 & 0x1F) << 16
    res |= imm & 0xFFFF
    return get_ins_bytes(res)


def ins_j(opcode: OpCode, rd: int, imm: int) -> bytes:
    res = (opcode.value & 0x3F) << 26
    res |= (rd & 0x1F) << 21
    res |= imm & 0x1FFFFF
    return get_ins_bytes(res)


def ins_s(opcode: OpCode, rs2: int, rs1: int, imm: int) -> bytes:
    res = (opcode.value & 0x3F) << 26
    res |= (rs2 & 0x1F) << 21
    res |= (rs1 & 0x1F) << 16
    res |= imm & 0xFFFF

    return get_ins_bytes(res)


def ins_u(opcode: OpCode, rd: int, imm: int) -> bytes:
    res = (opcode.value & 0x3F) << 26
    res |= (rd & 0x1F) << 21
    res |= imm & 0xFFFFF

    return get_ins_bytes(res)


def ins_sys(opcode: OpCode, imm: int = 0) -> bytes:
    res = (opcode.value & 0x3F) << 26
    res |= imm & 0x3FFFFFF
    return get_ins_bytes(res)


# higher 20 bits
def hi(val):
    return (val & 0xFFFFF000) >> 12


# lower 12 bits
def lo(val):
    return val & 0x00000FFF


def word_to_int(word):
    return word if word < 0x80000000 else word - 0x100000000
