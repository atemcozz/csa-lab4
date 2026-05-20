import machine.isa as isa
import machine.machine as m

import compiler.ir as ir


class BackendError(Exception):
    pass


class CompilerBackend:
    R_ZERO = 0
    R_RA = 1
    R_SP = 2
    R_T0 = 5
    R_T1 = 6
    R_T2 = 7
    R_FP = 8
    R_A0 = 10

    def __init__(self, ir_program: ir.Program):
        self.ir_program = ir_program
        self.word_size = 4

        self.text_base_address = 0x80
        self.current_pc = self.text_base_address

        # reserve 32 words for _start jmp + int table
        self.instructions = [isa.ins_i(m.OpCode.ADD, 0, 0, 0)] * 32

        self.labels = {}
        self.global_symbols = {}

        self.unresolved_jumps = []  # (instr_idx, target_label_name, instr_pc, opcode)
        self.unresolved_globals = []  # (instr_idx, global_name, type)

        self.frame = {}

        self.int_table_base = isa.INT_TABLE_BASE

        self.global_reg_map = {}
        self.GLOBAL_REGS_POOL = [21, 22, 23, 24, 25, 26, 27]
        self._current_ins_idx = 0

    def compile_binary(self):
        self.global_reg_map = {}
        available_global_vars_regs = list(self.GLOBAL_REGS_POOL)

        for node in self.ir_program.data:
            if isinstance(node, ir.GlobalVariable):
                # map global variable to register from global pool if possible
                if len(available_global_vars_regs) > 0:
                    reg = available_global_vars_regs.pop(0)
                    self.global_reg_map[node.name] = reg

                self.global_symbols[node.name] = "value"
            elif isinstance(node, (ir.GlobalArray, ir.StringData)):
                self.global_symbols[node.name] = "addr"
        # text section
        self.generate_text()
        # data section
        self.generate_data()

        # _start label with jal to main and halt
        self.generate_start()

        # patch unresolved jumps and globals
        self.patch_jumps_and_globals()
        # add jump to _start to 0x0
        self.patch_start_jump()

        self.setup_interrupt_table()

        binary = bytearray()
        for ins_bytes in self.instructions:
            binary.extend(ins_bytes)

        return binary, self.labels

    def emit(self, ins_bytes: bytes):
        self.instructions.append(ins_bytes)
        self.current_pc += self.word_size

    def is_function_label(self, name: str):
        return name.startswith("function_") or name in self.ir_program.interrupt_table.values()


    # get variables reads and writes values for a single ir node
    def get_reads_writes(self, node: ir.IRNode):
        reads = []
        writes = []
        self.get_rw_for_assign(node, reads, writes)
        self.get_rw_for_mem_io(node, reads, writes)
        if isinstance(node, ir.CondJump):
            reads.append(node.condition)
        elif isinstance(node, ir.Return) and node.value:
            reads.append(node.value)
        return reads, writes

    def get_rw_for_assign(self, node: ir.IRNode, reads: list, writes: list):
        if isinstance(node, ir.Assign):
            reads.append(node.src)
            writes.append(node.dest)
        elif isinstance(node, ir.BinOp):
            reads.extend([node.left, node.right])
            writes.append(node.dest)
        elif isinstance(node, ir.UnaryOp):
            reads.append(node.operand)
            writes.append(node.dest)
        elif isinstance(node, ir.Call):
            reads.extend(node.args)
            writes.append(node.dest)

    def get_rw_for_mem_io(self, node: ir.IRNode, reads: list, writes: list):
        if isinstance(node, ir.ReadIO):
            reads.append(node.port)
            writes.append(node.dest)
        elif isinstance(node, ir.WriteIO):
            reads.extend([node.value, node.port])
        elif isinstance(node, ir.Load):
            reads.extend([node.address, node.imm])
            writes.append(node.dest)
        elif isinstance(node, ir.Store):
            reads.extend([node.value, node.imm, node.address])

    def is_variable_name(self, val):
        if not isinstance(val, str):
            return False
        if val.startswith("$"):
            return True
        return True


    # scan variables inside function in a way to properly allocate stack for them later
    def scan_function_vars(self, start_idx):
        idx = start_idx + 1
        args = []
        local_vars = []
        # extra set for quick lookup
        local_vars_seen = set()
        array_sizes = {}

        while idx < len(self.ir_program.instructions):
            node = self.ir_program.instructions[idx]
            if isinstance(node, ir.Label) and self.is_function_label(node.name):
                break

            self.update_scan_from_node(node, args, local_vars, local_vars_seen, array_sizes)
            idx += 1

        return args, local_vars, array_sizes

    def update_scan_from_node(self, node: ir.IRNode, args: list, local_vars: list, local_vars_seen: set, array_sizes: dict):
        if isinstance(node, ir.LocalArrayAlloc):
            array_sizes[node.name] = node.size * 4
            if node.name not in local_vars_seen:
                local_vars.append(node.name)
                local_vars_seen.add(node.name)

        reads, writes = self.get_reads_writes(node)
        for r in reads:
            # variables that are not locals or globals vars can only be function args
            if self.is_variable_name(r) and r not in local_vars_seen and r not in args and r not in self.global_symbols:
                args.append(r)
        for w in writes:
            if isinstance(w, str) and w not in self.global_symbols and w not in local_vars_seen:
                local_vars.append(w)
                local_vars_seen.add(w)

    # prepare function frame layout (function args, local vars and arrays inside function)
    def prepare_function_frame(self, start_idx, is_interrupt=False):
        args, local_vars, array_sizes = self.scan_function_vars(start_idx)

        self.frame = {}
        array_data_offsets = {}
        offset = 24 if is_interrupt else 8

        for a in args:
            offset += 4
            self.frame[a] = -offset

        for l_var in local_vars:
            if l_var not in self.frame:
                if l_var in array_sizes:
                    offset += array_sizes[l_var]
                    self.frame[l_var] = -offset
                    array_data_offsets[l_var] = -offset
                else:
                    offset += 4
                    self.frame[l_var] = -offset

        return args, offset, array_data_offsets

    # emit corresponding operations for each IR node type
    def generate_text(self):
        self._is_int_function = False
        dispatch = {
            ir.Label:           self.emit_label,
            ir.Assign:          self.emit_assign,
            ir.BinOp:           self.emit_binop,
            ir.UnaryOp:         self.emit_unaryop,
            ir.Call:            self.emit_call,
            ir.Jump:            self.emit_jump,
            ir.CondJump:        self.emit_condjump,
            ir.ReadIO:          self.emit_read_io,
            ir.WriteIO:         self.emit_write_io,
            ir.Load:            self.emit_load,
            ir.Store:           self.emit_store,
            ir.Return:          self.emit_return,
            ir.LocalArrayAlloc: lambda _: None,
        }
        for idx, node in enumerate(self.ir_program.instructions):
            self._current_ins_idx = idx
            handler = dispatch.get(type(node))
            if handler:
                handler(node)

    # update local labels pointers and setup function call if label is function entry
    def emit_label(self, node: ir.Label):
        self.labels[node.name] = self.current_pc
        if not self.is_function_label(node.name):
            return
        self.frame = {}
        self._is_int_function = node.name in self.ir_program.interrupt_table.values()
        args, frame_size, array_data_offsets = self.prepare_function_frame(
            self._current_ins_idx, is_interrupt=self._is_int_function
        )
        self.emit_function_prologue(args, frame_size, array_data_offsets)

    # function prologue (allocate stack frame, save caller registers, set up frame pointer)
    def emit_function_prologue(self, args, frame_size, array_data_offsets):
        if self._is_int_function:
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_SP, self.R_SP, -24))
            self.emit(isa.ins_s(isa.OpCode.SW, self.R_RA, self.R_SP, 20))
            self.emit(isa.ins_s(isa.OpCode.SW, self.R_FP, self.R_SP, 16))
            self.emit(isa.ins_s(isa.OpCode.SW, self.R_T0, self.R_SP, 12))
            self.emit(isa.ins_s(isa.OpCode.SW, self.R_T1, self.R_SP, 8))
            self.emit(isa.ins_s(isa.OpCode.SW, self.R_T2, self.R_SP, 4))
            self.emit(isa.ins_s(isa.OpCode.SW, self.R_A0, self.R_SP, 0))
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_FP, self.R_SP, 24))
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_SP, self.R_SP, -frame_size))
        else:
            self.emit(isa.ins_s(isa.OpCode.SW, self.R_RA, self.R_SP, -4))
            self.emit(isa.ins_s(isa.OpCode.SW, self.R_FP, self.R_SP, -8))
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_FP, self.R_SP, -8))
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_SP, self.R_SP, -frame_size))
            for i, a in enumerate(args[:8]):
                self.emit(isa.ins_s(isa.OpCode.SW, self.R_A0 + i, self.R_FP, self.frame[a]))

        # save array base addresses to stack for arrays in data section
        for arr_name, data_offset in array_data_offsets.items():
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_T0, self.R_FP, data_offset))
            self.emit(isa.ins_s(isa.OpCode.SW, self.R_T0, self.R_FP, self.frame[arr_name]))

    def emit_assign(self, node: ir.Assign):
        self.emit_load_operand(self.R_T0, node.src)
        self.emit_store_variable(node.dest, self.R_T0)

    def emit_binop(self, node: ir.BinOp):
        self.emit_load_operand(self.R_T0, node.left)
        self.emit_load_operand(self.R_T1, node.right)
        self.emit_binop_op(node.op)
        self.emit_store_variable(node.dest, self.R_T2)

    def emit_binop_op(self, op: str):
        ops = {
            "+": isa.OpCode.ADD, "-": isa.OpCode.SUB, "*": isa.OpCode.MUL,
            "/": isa.OpCode.DIV, "%": isa.OpCode.REM, "&": isa.OpCode.AND,
            "|": isa.OpCode.OR,  "^": isa.OpCode.XOR, "<<": isa.OpCode.SLL,
            ">>": isa.OpCode.SRA,
        }
        if op in ops:
            self.emit(isa.ins_r(ops[op], self.R_T2, self.R_T0, self.R_T1))
        elif op == "&&":
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_T2, self.R_ZERO, 0))
            self.emit(isa.ins_b(isa.OpCode.BEQ, self.R_T0, self.R_ZERO, 3 * self.word_size))
            self.emit(isa.ins_b(isa.OpCode.BEQ, self.R_T1, self.R_ZERO, 2 * self.word_size))
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_T2, self.R_ZERO, 1))
        elif op == "||":
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_T2, self.R_ZERO, 1))
            self.emit(isa.ins_b(isa.OpCode.BNE, self.R_T0, self.R_ZERO, 3 * self.word_size))
            self.emit(isa.ins_b(isa.OpCode.BNE, self.R_T1, self.R_ZERO, 2 * self.word_size))
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_T2, self.R_ZERO, 0))
        elif op in ("<", ">", "<=", ">=", "==", "!="):
            self.emit_comparison(op)
        else:
            raise BackendError(f"Unsupported binary op: {op}")

    def emit_comparison(self, op: str):
        reg_a, reg_b = self.R_T0, self.R_T1
        cmp_opcodes = {
            "<": isa.OpCode.BLT, ">": isa.OpCode.BLT,
            "<=": isa.OpCode.BGE, ">=": isa.OpCode.BGE,
            "==": isa.OpCode.BEQ, "!=": isa.OpCode.BNE,
        }
        opcode = cmp_opcodes[op]
        if op in (">", "<="):
            reg_a, reg_b = self.R_T1, self.R_T0
        self.emit(isa.ins_b(opcode, reg_a, reg_b, 3 * self.word_size))
        self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_T2, self.R_ZERO, 0))
        self.emit(isa.ins_j(isa.OpCode.JAL, self.R_ZERO, 2 * self.word_size))
        self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_T2, self.R_ZERO, 1))

    def emit_unaryop(self, node: ir.UnaryOp):
        self.emit_load_operand(self.R_T1, node.operand)
        if node.op == "-":
            self.emit(isa.ins_r(isa.OpCode.SUB, self.R_T2, self.R_ZERO, self.R_T1))
        elif node.op == "!":
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_T2, self.R_ZERO, 1))
            self.emit(isa.ins_b(isa.OpCode.BEQ, self.R_T1, self.R_ZERO, 2 * self.word_size))
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_T2, self.R_ZERO, 0))
        elif node.op == "~":
            self.emit(isa.ins_r(isa.OpCode.NOT, self.R_T2, self.R_T1, 0))
        else:
            raise BackendError(f"Unsupported unary op: {node.op}")
        self.emit_store_variable(node.dest, self.R_T2)

    def emit_call(self, node: ir.Call):
        for i, arg in enumerate(node.args[:8]):
            self.emit_load_operand(self.R_A0 + i, arg)
        if node.func_name in self.labels:
            offset = self.labels[node.func_name] - self.current_pc
            self.emit(isa.ins_j(isa.OpCode.JAL, self.R_RA, offset))
        else:
            instr_pc = self.current_pc
            self.emit(isa.ins_j(isa.OpCode.JAL, self.R_RA, 0))
            self.unresolved_jumps.append((len(self.instructions) - 1, node.func_name, instr_pc, isa.OpCode.JAL))
        self.emit_store_variable(node.dest, self.R_A0)

    def emit_jump(self, node: ir.Jump):
        if node.target.name in self.labels:
            offset = self.labels[node.target.name] - self.current_pc
            self.emit(isa.ins_j(isa.OpCode.JAL, 0, offset))
        else:
            instr_pc = self.current_pc
            self.emit(isa.ins_j(isa.OpCode.JAL, 0, 0))
            self.unresolved_jumps.append((len(self.instructions) - 1, node.target.name, instr_pc, isa.OpCode.JAL))

    def emit_condjump(self, node: ir.CondJump):
        self.emit_load_operand(self.R_T0, node.condition)
        if node.target.name in self.labels:
            offset = self.labels[node.target.name] - self.current_pc
            self.emit(isa.ins_b(isa.OpCode.BEQ, self.R_T0, self.R_ZERO, offset))
        else:
            instr_pc = self.current_pc
            self.emit(isa.ins_b(isa.OpCode.BEQ, self.R_T0, self.R_ZERO, 0))
            self.unresolved_jumps.append((len(self.instructions) - 1, node.target.name, instr_pc, isa.OpCode.BEQ))

    def emit_read_io(self, node: ir.ReadIO):
        self.emit_load_operand(self.R_T1, node.port)
        self.emit(isa.ins_r(isa.OpCode.IN, self.R_T0, self.R_T1, 0))
        self.emit_store_variable(node.dest, self.R_T0)

    def emit_write_io(self, node: ir.WriteIO):
        self.emit_load_operand(self.R_T0, node.value)
        self.emit_load_operand(self.R_T1, node.port)
        self.emit(isa.ins_s(isa.OpCode.OUT, self.R_T0, self.R_T1, 0))

    def emit_load(self, node: ir.Load):
        self.emit_load_operand(self.R_T0, node.address)
        self.emit_load_operand(self.R_T1, node.imm)
        self.emit(isa.ins_i(isa.OpCode.SLLI, self.R_T1, self.R_T1, 2))
        self.emit(isa.ins_r(isa.OpCode.ADD, self.R_T2, self.R_T0, self.R_T1))
        self.emit(isa.ins_i(isa.OpCode.LW, self.R_T0, self.R_T2, 0))
        self.emit_store_variable(node.dest, self.R_T0)

    def emit_store(self, node: ir.Store):
        self.emit_load_operand(self.R_T0, node.address)
        self.emit_load_operand(self.R_T1, node.imm)
        self.emit(isa.ins_i(isa.OpCode.SLLI, self.R_T1, self.R_T1, 2))
        self.emit(isa.ins_r(isa.OpCode.ADD, self.R_T2, self.R_T0, self.R_T1))
        self.emit_load_operand(self.R_T0, node.value)
        self.emit(isa.ins_s(isa.OpCode.SW, self.R_T0, self.R_T2, 0))

    def emit_return(self, node: ir.Return):
        if node.value is not None:
            self.emit_load_operand(self.R_A0, node.value)
        if self._is_int_function:
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_SP, self.R_FP, -24))
            self.emit(isa.ins_i(isa.OpCode.LW, self.R_RA, self.R_SP, 20))
            self.emit(isa.ins_i(isa.OpCode.LW, self.R_FP, self.R_SP, 16))
            self.emit(isa.ins_i(isa.OpCode.LW, self.R_T0, self.R_SP, 12))
            self.emit(isa.ins_i(isa.OpCode.LW, self.R_T1, self.R_SP, 8))
            self.emit(isa.ins_i(isa.OpCode.LW, self.R_T2, self.R_SP, 4))
            self.emit(isa.ins_i(isa.OpCode.LW, self.R_A0, self.R_SP, 0))
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_SP, self.R_SP, 24))
            self.emit(isa.ins_sys(isa.OpCode.IRET))
        else:
            self.emit(isa.ins_i(isa.OpCode.ADDI, self.R_SP, self.R_FP, 8))
            self.emit(isa.ins_i(isa.OpCode.LW, self.R_FP, self.R_SP, -8))
            self.emit(isa.ins_i(isa.OpCode.LW, self.R_RA, self.R_SP, -4))
            self.emit(isa.ins_i(isa.OpCode.JALR, 0, self.R_RA, 0))

    # setup labels map and emit global arrays and strings data
    def generate_data(self):
        for node in self.ir_program.data:
            if isinstance(node, ir.GlobalVariable):
                self.labels[node.name] = self.current_pc
                val = node.initializer if node.initializer else 0
                self.emit(isa.get_ins_bytes(val))
            elif isinstance(node, ir.GlobalArray):
                self.labels[node.name] = self.current_pc
                for _ in range(node.size):
                    self.emit(isa.get_ins_bytes(0))
            elif isinstance(node, ir.StringData):
                self.labels[node.name] = self.current_pc

                length = len(node.value)
                self.emit(isa.get_ins_bytes(length))
                for c in node.value:
                    self.emit(isa.get_ins_bytes(ord(c)))

    # load 32-bit address by name into dest_reg
    def emit_load_address(self, dest_reg, name):
        lui_idx = len(self.instructions)
        self.emit(isa.ins_u(isa.OpCode.LUI, dest_reg, 0))
        addi_idx = len(self.instructions)
        self.emit(isa.ins_i(isa.OpCode.ADDI, dest_reg, dest_reg, 0))
        self.unresolved_globals.append((lui_idx, name, "addr_hi", dest_reg))
        self.unresolved_globals.append((addi_idx, name, "addr_lo", dest_reg))

    # load full 32-bit immediate into dest_reg
    def emit_load_immediate(self, dest_reg, value: int):
        value = value & m.WORD_MASK

        # extend sign
        signed = value if value < 0x80000000 else value - 0x100000000
        if -0x8000 <= signed <= 0x7FFF:
            self.emit(isa.ins_i(isa.OpCode.ADDI, dest_reg, self.R_ZERO, value & 0xFFFF))
            return

        lo = isa.lo(value)
        hi = isa.hi(value)
        if lo & 0x800:
            hi = (hi + 1) & 0xFFFFF

        self.emit(isa.ins_u(isa.OpCode.LUI, dest_reg, hi))

        if lo:
            signed_lo = lo if lo < 0x800 else lo - 0x1000
            self.emit(isa.ins_i(isa.OpCode.ADDI, dest_reg, dest_reg, signed_lo & 0xFFFF))

    # load imm, global variable or local variable into dest_reg
    def emit_load_operand(self, dest_reg, val):
        if isinstance(val, int):
            self.emit_load_immediate(dest_reg, val)
            return

        if isinstance(val, str):
            if val in self.frame:
                self.emit(isa.ins_i(isa.OpCode.LW, dest_reg, self.R_FP, self.frame[val]))
                return

            if val in self.global_reg_map:
                src_reg = self.global_reg_map[val]
                self.emit(isa.ins_r(isa.OpCode.ADD, dest_reg, src_reg, self.R_ZERO))
                return

            if val in self.global_symbols:
                self.emit_load_address(dest_reg, val)
                if self.global_symbols[val] == "value":
                    self.emit(isa.ins_i(isa.OpCode.LW, dest_reg, dest_reg, 0))
                return

            self.emit(isa.ins_i(isa.OpCode.ADDI, dest_reg, self.R_ZERO, 0))

    def emit_store_variable(self, dest, src_reg):
        if dest in self.frame:
            self.emit(isa.ins_s(isa.OpCode.SW, src_reg, self.R_FP, self.frame[dest]))
        elif dest in self.global_reg_map:
            dest_reg = self.global_reg_map[dest]
            self.emit(isa.ins_r(isa.OpCode.ADD, dest_reg, src_reg, self.R_ZERO))

        elif dest in self.global_symbols:
            self.emit_load_address(self.R_T2, dest)
            self.emit(isa.ins_s(isa.OpCode.SW, src_reg, self.R_T2, 0))

    def patch_jump(self, idx, target, pc, opcode):
        if target not in self.labels:
            raise BackendError(f"Undefined label: {target}")
        offset = self.labels[target] - pc
        if opcode == m.OpCode.JAL:
            is_func = self.is_function_label(target)
            self.instructions[idx] = isa.ins_j(opcode, self.R_RA if is_func else 0, offset)
        elif opcode == m.OpCode.BEQ:
            self.instructions[idx] = isa.ins_b(opcode, self.R_T0, self.R_ZERO, offset)

    def patch_global(self, idx, name, patch_type, rd):
        if name not in self.labels:
            raise BackendError(f"Undefined global: {name}")

        addr = self.labels[name]
        lo = isa.lo(addr)
        hi = isa.hi(addr)

        if lo & 0x800:
            hi = (hi + 1) & 0xFFFFF
        signed_lo = lo if lo < 0x800 else lo - 0x1000

        if patch_type == "addr_hi":
            self.instructions[idx] = isa.ins_u(isa.OpCode.LUI, rd, hi)
        elif patch_type == "addr_lo":
            self.instructions[idx] = isa.ins_i(isa.OpCode.ADDI, rd, rd, signed_lo & 0xFFFF)

    def patch_jumps_and_globals(self):
        for idx, target, pc, opcode in self.unresolved_jumps:
            self.patch_jump(idx, target, pc, opcode)

        for idx, name, patch_type, rd in self.unresolved_globals:
            self.patch_global(idx, name, patch_type, rd)

    def generate_start(self):
        self.labels["_start"] = self.current_pc

        for name, reg in self.global_reg_map.items():
            self.emit_load_address(reg, name)
            self.emit(isa.ins_i(isa.OpCode.LW, reg, reg, 0))

        entry = self.ir_program.entry_point
        if entry in self.labels:
            offset = self.labels[entry] - self.current_pc
            self.emit(isa.ins_j(isa.OpCode.JAL, self.R_RA, offset))

        self.emit(isa.ins_sys(isa.OpCode.HALT))

    def patch_start_jump(self):
        if "_start" in self.labels:
            offset = self.labels["_start"]
            self.instructions[0] = isa.ins_j(isa.OpCode.JAL, 0, offset)

    def setup_interrupt_table(self):
        int_table_base_idx = self.int_table_base // 4
        for vec_idx, label in self.ir_program.interrupt_table.items():
            if label in self.labels:
                handler_addr = self.labels[label]
                self.instructions[int_table_base_idx + vec_idx] = isa.get_ins_bytes(handler_addr)
