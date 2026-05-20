from __future__ import annotations

import copy
from enum import Enum

from machine.isa import (
    B_OPCODES,
    INT_TABLE_BASE,
    IO_INPUT_PORTS_COUNT,
    IO_OUTPUT_PORTS_COUNT,
    J_OPCODES,
    REGISTERS_COUNT,
    REGS_NAMES,
    S_OPCODES,
    U_OPCODES,
    WORD_MASK,
    WORD_SIZE,
    CUState,
    OpCode,
    Regs,
    parse_instr_mnemonic,
)


class MachineError(Exception):
    pass


class PcMuxSelect(Enum):
    INC = 0
    BRANCH = 1
    ALU = 2
    EPC = 3

class ArMuxSelect(Enum):
    PC = 0
    ALU = 1
    IVT = 2

class RegWriteMuxSelect(Enum):
    ALU = 0
    DR = 1
    PC_INC = 2

class AluRightMuxSelect(Enum):
    RS2 = 0
    IMM = 1
    DR = 2

class AluOperation(Enum):
    ADD = 0
    SUB = 1
    AND = 2
    OR = 3
    XOR = 4
    NOT = 5
    SLL = 6
    SRL = 7
    SRA = 8
    MUL = 9
    DIV = 10
    REM = 11


class ALU:
    SIGN_MASK = 0x80000000

    def __init__(self):
        self.n = 0
        self.z = 0
        self.v = 0

    def num_to_signed(self, num):
        num &= WORD_MASK
        return num if num < self.SIGN_MASK else num - 0x100000000

    def calculate(self, operation, left, right):
        res = 0
        match operation:
            case AluOperation.ADD:
                res = left + right
                sa = (left >> 31) & 1
                sb = (right >> 31) & 1
                sr = (res >> 31) & 1
                self.v = (sa == sb) and (sr != sa)
            case AluOperation.SUB:
                res = left - right
                sa = (left >> 31) & 1
                sb = (right >> 31) & 1
                sr = (res >> 31) & 1
                self.v = (sa != sb) and (sr != sa)
            case AluOperation.AND:
                res = left & right
            case AluOperation.OR:
                res = left | right
            case AluOperation.XOR:
                res = left ^ right
            case AluOperation.SLL:
                res = left << (right & 0x1F)
            case AluOperation.SRL:
                res = (left & WORD_MASK) >> right
            case AluOperation.SRA:
                res = self.num_to_signed(left) >> (right & 0x1F)
            case AluOperation.MUL:
                res = left * right
            case AluOperation.DIV:
                if right == 0:
                    res = 0
                else:
                    signed_left = self.num_to_signed(left)
                    signed_right = self.num_to_signed(right)
                    res = int(signed_left / signed_right)
            case AluOperation.REM:
                if right == 0:
                    res = 0
                else:
                    signed_left = self.num_to_signed(left)
                    signed_right = self.num_to_signed(right)
                    res = signed_left % signed_right
            case AluOperation.NOT:
                res = ~left
            case _:
                raise MachineError(f"Invalid or unimplemented ALU operation: {operation}")

        res &= WORD_MASK
        self.n = (res >> 31) & 1
        self.z = 1 if res == 0 else 0
        return res



class DataPath:
    def __init__(self, memory_size):
        self.memory_size = memory_size
        self.memory = bytearray(memory_size)
        self.registers = [0] * REGISTERS_COUNT
        self.pc = 0
        self.next_pc = 0
        self.ar = 0
        self.dr = 0
        self.ir = 0
        self.alu = ALU()
        self.alu_out = 0
        self.imm = 0
        self.epc = 0
        self.registers[Regs.sp.value] = memory_size

    def signal_latch_epc(self, value):
        self.epc = value & WORD_MASK

    def signal_latch_ar(self, mux_select: ArMuxSelect, irq_vec=0):
        match mux_select:
            case ArMuxSelect.PC:
                self.ar = self.pc
            case ArMuxSelect.ALU:
                self.ar = self.alu_out
            case ArMuxSelect.IVT:
                self.ar = (INT_TABLE_BASE + (irq_vec << 2)) & WORD_MASK

    def signal_latch_ir(self):
        self.ir = self.dr

    def signal_mem_read_word(self):
        self.dr = int.from_bytes(bytes(self.memory[self.ar : self.ar + WORD_SIZE]), "little")

    def signal_mem_write_word(self):
        self.memory[self.ar : self.ar + WORD_SIZE] = (self.dr & WORD_MASK).to_bytes(WORD_SIZE, "little")

    def signal_reg_read(self, reg1_idx, reg2_idx):
        assert 0 <= reg1_idx < REGISTERS_COUNT, f"Invalid register index: {reg1_idx}"
        assert 0 <= reg2_idx < REGISTERS_COUNT, f"Invalid register index: {reg2_idx}"

        # r0 hardwired to 0
        reg1 = 0 if reg1_idx == 0 else self.registers[reg1_idx]
        reg2 = 0 if reg2_idx == 0 else self.registers[reg2_idx]

        return reg1, reg2

    def signal_reg_write(self, reg_idx, mux_select: RegWriteMuxSelect):
        if reg_idx == 0:
            return

        match mux_select:
            case RegWriteMuxSelect.ALU:
                val = self.alu_out
            case RegWriteMuxSelect.DR:
                val = self.dr
            case RegWriteMuxSelect.PC_INC:
                val = self.next_pc

        self.registers[reg_idx] = val & WORD_MASK


    def signal_alu_calculate(self, operation, left, right, right_mux: AluRightMuxSelect = AluRightMuxSelect.RS2):
        right_val = None
        if right_mux == AluRightMuxSelect.RS2:
            right_val = right
        elif right_mux == AluRightMuxSelect.IMM:
            right_val = self.imm
        elif right_mux == AluRightMuxSelect.DR:
            right_val = self.dr

        self.alu_out = self.alu.calculate(operation, left, right_val)

    def signal_read_alu_flag_signals(self):
        return self.alu.n, self.alu.z, self.alu.v

    def signal_latch_pc(self, mux_select: PcMuxSelect):
        self.next_pc = (self.pc + WORD_SIZE) & WORD_MASK
        match mux_select:
            case PcMuxSelect.INC:
                self.pc = self.next_pc
            case PcMuxSelect.BRANCH:
                self.pc = (self.pc + self.imm) & WORD_MASK
            case PcMuxSelect.ALU:
                self.pc = self.alu_out
            case PcMuxSelect.EPC:
                self.pc = self.epc

    def signal_latch_dr(self, value):
        self.dr = value & WORD_MASK

    def signal_latch_imm(self, value):
        self.imm = value & WORD_MASK

    def __repr__(self):
        registers_state = " ".join([f"{REGS_NAMES[i]}:{val}" for i, val in enumerate(self.registers)])
        return f"PC:{self.pc} AR:{self.ar} DR:{self.dr} IR:{self.ir} {registers_state}"

    def get_memory_dump(self, start=0, end=None):
        s = ""
        end = end if end is not None else self.memory_size

        for addr in range(start, end, WORD_SIZE):
            s += f"0x{addr:08x} | "
            for offset in range(WORD_SIZE):
                if addr + offset < self.memory_size:
                    s += f"{self.memory[addr + offset]:02x} "
            instr = int.from_bytes(bytes(self.memory[addr : addr + WORD_SIZE]), "little")

            s += "| " + parse_instr_mnemonic(instr) + "\n"
        return s


class IOController:
    def __init__(self, input_schedule: dict[int, list[tuple[int, int]]]):
        self.in_ports = [0] * IO_INPUT_PORTS_COUNT
        self.out_ports = [[] for _ in range(IO_OUTPUT_PORTS_COUNT)]

        self.input_schedule = copy.deepcopy(input_schedule)

        self.irq = 0
        self.irq_vector = 0

        self.port_pending = [False] * IO_INPUT_PORTS_COUNT

    def signal_read_irq(self, tick):
        for i in range(len(self.in_ports)):
            port_schedule = self.input_schedule.get(i, [])
            last_val = None
            while port_schedule and tick >= port_schedule[0][0]:
                _, last_val = port_schedule.pop(0)

            if last_val is not None:
                self.in_ports[i] = last_val
                self.port_pending[i] = True

        for i in range(len(self.in_ports)):
            if self.port_pending[i]:
                self.irq = 1
                self.irq_vector = i
                return self.irq

        self.irq = 0
        return self.irq

    def signal_read_irq_vector(self):
        return self.irq_vector

    def signal_read_port(self, port_idx):
        assert 0 <= port_idx < len(self.in_ports), f"Invalid io port index: {port_idx}"
        val = self.in_ports[port_idx] & 0xFFFFFFFF
        self.port_pending[port_idx] = False
        self.irq = 0
        return val

    def signal_write_port(self, port_idx, value):
        assert 0 <= port_idx < len(self.out_ports), f"Invalid io port index: {port_idx}"
        val = value & 0xFFFFFFFF
        self.out_ports[port_idx].insert(0, val)

    def __repr__(self):
        in_hex = [f"0x{val & 0xFFFFFFFF:08x}" for val in self.in_ports]
        out_hex = [[f"0x{val & 0xFFFFFFFF:08x}" for val in buf] for buf in self.out_ports]

        in_chr = ["'{}'".format(chr(val) if 0 <= val <= 127 else "?") for val in self.in_ports]
        out_chr = [["'{}'".format(chr(val) if 0 <= val <= 127 else "?") for val in buf] for buf in self.out_ports]

        in_ports_state = "in(hex): [{}] | in(chr): [{}] ".format(", ".join(in_hex), ", ".join(in_chr))

        out_ports_state = "out(hex): [{}] | out(chr): [{}]".format(
            ", ".join("[" + " ".join(buf) + "]" for buf in out_hex),
            ", ".join("[" + " ".join(buf) + "]" for buf in out_chr),
        )
        return f"{in_ports_state}\n{out_ports_state}"


class ControlUnit:
    def __init__(self, datapath: DataPath, io_controller: IOController):
        self._tick = 0
        self.halt = 0
        self.datapath = datapath
        self.state = CUState.FETCH
        self.int = 0  # interrupt flag
        self.ie = 1  # enable interrupts

        self.opcode = None

        self.rs1_idx = 0
        self.rs2_idx = 0
        self.rd_idx = 0

        self.io_controller = io_controller

    def tick(self):
        self._tick += 1

    def current_tick(self):
        return self._tick

    def sign_extend(self, value, bits):
        sign_bit = 1 << (bits - 1)
        return (value & (sign_bit - 1)) - (value & sign_bit)

    def process_next_tick(self):
        if self.halt:
            return
        self.tick()

        if self.state == CUState.FETCH and self.ie:
            # check for pending interrupts from io controller
            if self.io_controller.signal_read_irq(self._tick):
                self.state = CUState.TRAP
                self.process_state_trap()
                return

        match self.state:
            case CUState.FETCH:
                self.process_state_fetch()
            case CUState.DECODE:
                self.process_state_decode()
            case CUState.EXECUTE:
                self.process_state_execute()
            case CUState.MEMORY:
                self.process_state_memory()
            case CUState.WRITEBACK:
                self.process_state_writeback()
            case CUState.TRAP:
                self.process_state_trap()
            case CUState.TRAP_MEMORY:
                self.process_state_trap_memory()
            case CUState.TRAP_WRITEBACK:
                self.process_state_trap_writeback()
            case _:
                raise MachineError(f"Invalid control unit state: {self.state}")

    def process_state_fetch(self):
        self.datapath.signal_latch_ar(ArMuxSelect.PC)
        self.datapath.signal_mem_read_word()
        self.datapath.signal_latch_ir()
        self.state = CUState.DECODE

    def process_state_decode(self):
        ir = self.datapath.ir
        opcode_bits = (ir >> 26) & 0x3F
        self.opcode = OpCode(opcode_bits)

        self.rd_idx = (ir >> 21) & 0x1F
        self.rs1_idx = (ir >> 16) & 0x1F
        self.rs2_idx = (ir >> 11) & 0x1F

        if self.opcode in B_OPCODES:
            self.rd_idx = 0
            self.rs1_idx = (ir >> 21) & 0x1F
            self.rs2_idx = (ir >> 16) & 0x1F

        elif self.opcode in S_OPCODES:
            self.rd_idx = 0
            self.rs2_idx = (ir >> 21) & 0x1F
            self.rs1_idx = (ir >> 16) & 0x1F


        # imm bits for different types of instructions

        if self.opcode in J_OPCODES:
            self.imm = self.sign_extend(ir & 0x1FFFFF, 21)
        elif self.opcode in U_OPCODES:
            self.imm = (ir & 0xFFFFF) << 12
        else:
            self.imm = self.sign_extend(ir & 0xFFFF, 16)

        self.datapath.signal_latch_imm(self.imm)

        self.state = CUState.EXECUTE

    def process_state_execute(self):
        rs1, rs2 = self.datapath.signal_reg_read(self.rs1_idx, self.rs2_idx)

        match self.opcode:
            case OpCode.ADD:
                self.datapath.signal_alu_calculate(AluOperation.ADD, rs1, rs2)
                self.state = CUState.WRITEBACK

            case OpCode.SUB:
                self.datapath.signal_alu_calculate(AluOperation.SUB, rs1, rs2)
                self.state = CUState.WRITEBACK

            case OpCode.MUL:
                self.datapath.signal_alu_calculate(AluOperation.MUL, rs1, rs2)
                self.state = CUState.WRITEBACK

            case OpCode.DIV:
                self.datapath.signal_alu_calculate(AluOperation.DIV, rs1, rs2)
                self.state = CUState.WRITEBACK

            case OpCode.REM:
                self.datapath.signal_alu_calculate(AluOperation.REM, rs1, rs2)
                self.state = CUState.WRITEBACK

            case OpCode.ADDI:
                self.datapath.signal_alu_calculate(AluOperation.ADD, rs1, self.imm)
                self.state = CUState.WRITEBACK

            case OpCode.SLLI:
                self.datapath.signal_alu_calculate(AluOperation.SLL, rs1, self.imm)
                self.state = CUState.WRITEBACK

            case OpCode.AND:
                self.datapath.signal_alu_calculate(AluOperation.AND, rs1, rs2)
                self.state = CUState.WRITEBACK

            case OpCode.OR:
                self.datapath.signal_alu_calculate(AluOperation.OR, rs1, rs2)
                self.state = CUState.WRITEBACK

            case OpCode.XOR:
                self.datapath.signal_alu_calculate(AluOperation.XOR, rs1, rs2)
                self.state = CUState.WRITEBACK

            case OpCode.SLL:
                self.datapath.signal_alu_calculate(AluOperation.SLL, rs1, rs2)
                self.state = CUState.WRITEBACK

            case OpCode.SRL:
                self.datapath.signal_alu_calculate(AluOperation.SRL, rs1, rs2)
                self.state = CUState.WRITEBACK

            case OpCode.SRA:
                self.datapath.signal_alu_calculate(AluOperation.SRA, rs1, rs2)
                self.state = CUState.WRITEBACK

            case OpCode.NOT:
                self.datapath.signal_alu_calculate(AluOperation.NOT, rs1, 0)
                self.state = CUState.WRITEBACK

            case OpCode.LW:
                # rs1 + imm -> ar
                self.datapath.signal_alu_calculate(AluOperation.ADD, rs1, self.imm)
                self.datapath.signal_latch_ar(ArMuxSelect.ALU)
                self.state = CUState.MEMORY

            case OpCode.SW:
                # rs1 + imm -> ar, rs2 -> dr
                self.datapath.signal_alu_calculate(AluOperation.ADD, rs1, self.imm)
                self.datapath.signal_latch_ar(ArMuxSelect.ALU)
                self.datapath.signal_latch_dr(rs2)
                self.state = CUState.MEMORY

            case OpCode.BEQ:
                # alu sub; if r == 0: pc + imm -> pc
                self.datapath.signal_alu_calculate(AluOperation.SUB, rs1, rs2)
                _, z, _ = self.datapath.signal_read_alu_flag_signals()
                if z == 1:
                    self.datapath.signal_latch_pc(PcMuxSelect.BRANCH)
                else:
                    self.datapath.signal_latch_pc(PcMuxSelect.INC)
                self.state = CUState.FETCH

            case OpCode.BNE:
                # alu sub; if r != 0: pc + imm -> pc
                self.datapath.signal_alu_calculate(AluOperation.SUB, rs1, rs2)
                _, z, _ = self.datapath.signal_read_alu_flag_signals()
                if z == 0:
                    self.datapath.signal_latch_pc(PcMuxSelect.BRANCH)
                else:
                    self.datapath.signal_latch_pc(PcMuxSelect.INC)
                self.state = CUState.FETCH

            case OpCode.BLT:
                # alu sub; if N ^ V == 1: pc + imm -> pc
                self.datapath.signal_alu_calculate(AluOperation.SUB, rs1, rs2)
                n, _, v = self.datapath.signal_read_alu_flag_signals()
                if (n ^ v) == 1:
                    self.datapath.signal_latch_pc(PcMuxSelect.BRANCH)
                else:
                    self.datapath.signal_latch_pc(PcMuxSelect.INC)
                self.state = CUState.FETCH

            case OpCode.BGE:
                self.datapath.signal_alu_calculate(AluOperation.SUB, rs1, rs2)
                n, _, v = self.datapath.signal_read_alu_flag_signals()
                if (n ^ v) == 0:
                    self.datapath.signal_latch_pc(PcMuxSelect.BRANCH)
                else:
                    self.datapath.signal_latch_pc(PcMuxSelect.INC)
                self.state = CUState.FETCH

            case OpCode.JAL:
                self.datapath.signal_latch_pc(PcMuxSelect.BRANCH)
                self.state = CUState.WRITEBACK
            case OpCode.JALR:
                self.datapath.signal_alu_calculate(AluOperation.ADD, rs1, 0, AluRightMuxSelect.IMM)
                self.datapath.signal_latch_pc(PcMuxSelect.ALU)
                self.state = CUState.WRITEBACK

            case OpCode.IN:
                rs1, _ = self.datapath.signal_reg_read(self.rs1_idx, 0)
                self.datapath.signal_alu_calculate(AluOperation.ADD, rs1, 0)

                self.datapath.signal_latch_ar(ArMuxSelect.ALU)
                self.state = CUState.MEMORY

            case OpCode.OUT:
                rs1, rs2 = self.datapath.signal_reg_read(self.rs1_idx, self.rs2_idx)
                self.datapath.signal_alu_calculate(AluOperation.ADD, rs1, 0)

                self.datapath.signal_latch_ar(ArMuxSelect.ALU)
                self.datapath.signal_latch_dr(rs2)
                self.state = CUState.MEMORY

            case OpCode.EI:
                self.ie = 1
                self.datapath.signal_latch_pc(PcMuxSelect.INC)
                self.state = CUState.FETCH

            case OpCode.DI:
                self.ie = 0
                self.datapath.signal_latch_pc(PcMuxSelect.INC)
                self.state = CUState.FETCH

            case OpCode.IRET:
                self.ie = 1
                self.int = 0
                self.datapath.signal_latch_pc(PcMuxSelect.EPC)
                self.state = CUState.FETCH
            case OpCode.HALT:
                self.halt = 1
                self.state = CUState.FETCH
            case OpCode.LUI:
                self.datapath.signal_alu_calculate(AluOperation.ADD, 0, 0, AluRightMuxSelect.IMM)
                self.state = CUState.WRITEBACK
            case _:
                raise MachineError(f"Unsupported/unimplemented opcode in execute: {self.opcode}")

    def process_state_memory(self):
        match self.opcode:
            case OpCode.LW:
                self.datapath.signal_mem_read_word()
                self.state = CUState.WRITEBACK

            case OpCode.SW:
                self.datapath.signal_mem_write_word()
                self.datapath.signal_latch_pc(PcMuxSelect.INC)
                self.state = CUState.FETCH
            case OpCode.IN:
                val = self.io_controller.signal_read_port(self.datapath.ar)
                self.datapath.signal_latch_dr(val)
                self.state = CUState.WRITEBACK

            case OpCode.OUT:
                val = self.io_controller.signal_write_port(self.datapath.ar, self.datapath.dr)
                self.datapath.signal_latch_pc(PcMuxSelect.INC)
                self.state = CUState.FETCH
            case _:
                raise MachineError(f"Unsupported/unimplemented opcode in memory stage: {self.opcode}")

    def process_state_writeback(self):
        match self.opcode:
            case (
                OpCode.ADD
                | OpCode.ADDI
                | OpCode.SLLI
                | OpCode.SUB
                | OpCode.MUL
                | OpCode.DIV
                | OpCode.REM
                | OpCode.AND
                | OpCode.OR
                | OpCode.XOR
                | OpCode.SLL
                | OpCode.SRL
                | OpCode.SRA
                | OpCode.NOT
            ):
                self.datapath.signal_reg_write(self.rd_idx, RegWriteMuxSelect.ALU)
                self.datapath.signal_latch_pc(PcMuxSelect.INC)
                self.state = CUState.FETCH
            case OpCode.JAL | OpCode.JALR:
                # restore saved return address
                self.datapath.signal_reg_write(self.rd_idx, RegWriteMuxSelect.PC_INC)
                self.state = CUState.FETCH

            case OpCode.IN | OpCode.LW:
                self.datapath.signal_reg_write(self.rd_idx, RegWriteMuxSelect.DR)
                self.datapath.signal_latch_pc(PcMuxSelect.INC)
                self.state = CUState.FETCH

            case OpCode.LUI:
                self.datapath.signal_reg_write(self.rd_idx, RegWriteMuxSelect.ALU)
                self.datapath.signal_latch_pc(PcMuxSelect.INC)
                self.state = CUState.FETCH
            case _:
                raise MachineError(f"Unimplemented opcode: {self.opcode}")

    def process_state_trap(self):
        self.int = 1
        # disable nested interrupts
        self.ie = 0

        self.datapath.signal_latch_epc(self.datapath.pc)

        irq_vec = self.io_controller.signal_read_irq_vector()

        self.datapath.signal_latch_ar(ArMuxSelect.IVT, irq_vec)

        self.state = CUState.TRAP_MEMORY

    def process_state_trap_memory(self):
        self.datapath.signal_mem_read_word()
        self.state = CUState.TRAP_WRITEBACK

    def process_state_trap_writeback(self):
        self.datapath.signal_alu_calculate(AluOperation.ADD, 0, 0, AluRightMuxSelect.DR)
        self.datapath.signal_latch_pc(PcMuxSelect.ALU)
        self.state = CUState.FETCH

    def __repr__(self):
        s = f"TICK:{self._tick:4} | {self.state.name:9} "

        mnemonic = parse_instr_mnemonic(self.datapath.ir)
        s += f"| {mnemonic:18} "

        if self.int:
            s += "| INT "
        s += f"| {self.datapath}"

        return s





