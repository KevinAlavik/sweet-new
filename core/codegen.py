from core.parser import *
from core.lexer import *

class CodegenException(Exception):
    def __init__(self, msg):
        print(f"Codegen Error: {msg}")
        exit(1)

class CodeGen:
    def __init__(self):
        self.output = []
        self.label_count = 0
        self.string_literals = {}
        self.string_label_count = 0
        self.current_function = None
        self.var_offsets = {}
        self.stack_size = 0
        self.global_vars = []
        self.externs = []
        self.global_symbols = []

    def unique_label(self, base="L"):
        self.label_count += 1
        return f"{base}{self.label_count}"

    def get_string_label(self, s):
        if s not in self.string_literals:
            self.string_label_count += 1
            label = f"LC{self.string_label_count}"
            self.string_literals[s] = label
        return self.string_literals[s]

    def emit(self, instruction, indent=4):
        self.output.append(f"{' ' * indent}{instruction}")

    def emit_section(self, section_name):
        self.output.append(f"section .{section_name}")

    def emit_label(self, label):
        self.output.append(f"{label}:")

    def prologue(self):
        self.emit("push rbp")
        self.emit("mov rbp, rsp")
        if self.stack_size > 0:
            aligned_size = ((self.stack_size + 15) // 16) * 16
            if aligned_size != 0:
                self.emit(f"sub rsp, {aligned_size}")
                self.stack_size = aligned_size

    def epilogue(self):
        self.emit("mov rsp, rbp")
        self.emit("pop rbp")
        self.emit("ret")

    def generate(self, ast_nodes):
        for node in ast_nodes:
            if isinstance(node, VariableDef) and self.current_function is None:
                self.global_vars.append(node)
                self.global_symbols.append(node.name)
            elif isinstance(node, ExternDecl):
                self.externs.append(node.name)
            elif isinstance(node, FunctionDef):
                self.global_symbols.append(node.name)

        self.emit("default rel")
        for symbol in self.global_symbols:
            self.emit(f"global {symbol}")
        for ext in self.externs:
            self.emit(f"extern {ext}")

        if self.global_vars:
            self.emit_section("data")
            for gvar in self.global_vars:
                if gvar.value is None:
                    continue
                label = gvar.name
                if isinstance(gvar.value, NumberLiteral):
                    self.emit(f"{label}: dq {gvar.value.value}")
                elif isinstance(gvar.value, StringLiteral):
                    str_label = self.get_string_label(gvar.value.value)
                    self.emit(f"{label}: dq {str_label}")
                else:
                    self.emit(f"{label}: dq 0")

            uninit_globals = [g for g in self.global_vars if g.value is None]
            if uninit_globals:
                self.emit_section("bss")
                for gvar in uninit_globals:
                    self.emit(f"{gvar.name}: resq 1")

        self.emit_section("text")
        for node in ast_nodes:
            if isinstance(node, FunctionDef):
                self._codegen_dispatch(node)
            elif isinstance(node, ExternDecl) or (isinstance(node, VariableDef) and self.current_function is None):
                continue
            else:
                self._codegen_dispatch(node)

        if self.string_literals:
            self.emit_section("rodata")
            for s, label in self.string_literals.items():
                try:
                    interpreted = s.encode('utf-8').decode('unicode_escape').encode('latin1')
                except UnicodeEncodeError:
                    raise CodegenException(f"Invalid character in string literal: {repr(s)}")
                ascii_bytes = ', '.join(str(b) for b in interpreted)
                self.emit(f"{label}: db {ascii_bytes}, 0")

        return "\n".join(self.output)

    def _codegen_dispatch(self, node):
        handlers = {
            ExternDecl: self._codegen_extern,
            FunctionDef: self._codegen_function,
            VariableDef: self._codegen_variable_def,
            ReturnNode: self._codegen_return,
            FunctionCall: self._codegen_function_call,
            Assignment: self._codegen_assignment,
            BinaryOp: self._codegen_binary_op,
            NumberLiteral: lambda n: self._codegen_expression(n, 'rax'),
            StringLiteral: lambda n: self._codegen_expression(n, 'rax'),
            BooleanLiteral: lambda n: self._codegen_expression(n, 'rax'),
            VariableAccess: lambda n: self._codegen_expression(n, 'rax'),
        }
        handler = handlers.get(type(node))
        if handler:
            handler(node)
        else:
            raise CodegenException(f"Codegen for {type(node).__name__} not implemented")

    def _codegen_extern(self, node):
        pass

    def _codegen_function(self, node):
        self.current_function = node
        self.var_offsets = {}
        self.stack_size = 0

        self.emit_label(node.name)

        offset = 0
        for var in node.body:
            if isinstance(var, VariableDef):
                if hasattr(var.type_, "array_size") and var.type_.array_size is not None:
                    raise CodegenException("Arrays are not supported")
                offset += 8
                self.var_offsets[var.name] = -offset
        self.stack_size = offset

        self.prologue()

        param_regs = ['rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9']
        for i, param in enumerate(node.parameters):
            if i < 6:
                off = self.var_offsets.get(param.name)
                if off is None:
                    offset += 8
                    off = -offset
                    self.var_offsets[param.name] = off
                    self.stack_size = offset
                    aligned_stack = ((self.stack_size + 15) // 16) * 16
                    if aligned_stack != self.stack_size:
                        diff = aligned_stack - self.stack_size
                        self.emit(f"sub rsp, {diff}")
                        self.stack_size = aligned_stack

                self.emit(f"mov [rbp{off}], {param_regs[i]}")

            else:
                raise CodegenException("More than 6 parameters not supported")

        for stmt in node.body:
            self._codegen_dispatch(stmt)

        if not any(isinstance(s, ReturnNode) for s in node.body):
            self.epilogue()

        self.current_function = None
        self.var_offsets = {}
        self.stack_size = 0

    def _codegen_variable_def(self, node):
        if self.current_function:
            if hasattr(node.type_, "array_size") and node.type_.array_size is not None:
                raise CodegenException("Arrays are not supported")
            if node.value is not None:
                self._codegen_expression(node.value, 'rax')
                offset = self.var_offsets[node.name]
                self.emit(f"mov [rbp{offset}], rax")

    def _codegen_return(self, node):
        if node.expression:
            self._codegen_expression(node.expression, 'rax')
        else:
            self.emit("mov rax, 0")
        self.epilogue()

    def _codegen_assignment(self, node):
        if hasattr(node.name, "index") and node.name.index is not None:
            raise CodegenException("Array indexing is not supported")
        self._codegen_expression(node.value, 'rax')
        offset = self.var_offsets[node.name]
        self.emit(f"mov [rbp{offset}], rax")

    def _codegen_function_call(self, node):
        arg_regs = ['rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9']
        argc = len(node.arguments)

        stack_args = max(0, argc - 6)
        adjustment = 0
        if (stack_args % 2) != 0:
            adjustment = 8
            self.emit(f"sub rsp, {adjustment}")

        for i in reversed(range(6, argc)):
            self._codegen_expression(node.arguments[i], 'rax')
            self.emit("push rax")

        for i in range(min(6, argc)):
            self._codegen_expression(node.arguments[i], 'rax')
            self.emit(f"mov {arg_regs[i]}, rax")

        self.emit("xor rax, rax")
        self.emit(f"call {node.name}")

        if stack_args > 0:
            self.emit(f"add rsp, {stack_args * 8}")

        if adjustment:
            self.emit(f"add rsp, {adjustment}")


    def _codegen_expression(self, node, target_reg='rax'):
        if isinstance(node, NumberLiteral):
            self.emit(f"mov {target_reg}, {node.value}")
        elif isinstance(node, StringLiteral):
            label = self.get_string_label(node.value)
            self.emit(f"lea {target_reg}, [rel {label}]")
        elif isinstance(node, BooleanLiteral):
            self.emit(f"mov {target_reg}, {1 if node.value == "true" else 0}")

        elif isinstance(node, VariableAccess):
            if hasattr(node, 'index') and node.index is not None:
                raise CodegenException("Array indexing is not supported")
            if len(node.parts) == 1:
                var_name = node.parts[0]
                if self.current_function and var_name in self.var_offsets:
                    offset = self.var_offsets[var_name]
                    self.emit(f"mov {target_reg}, [rbp{offset}]")
                else:
                    self.emit(f"mov {target_reg}, [{var_name}]")
            elif len(node.parts) == 2:
                member = node.parts[1]
                if member == "len":
                    raise CodegenException("`.len` property is not supported")
                else:
                    raise CodegenException("Struct member access not implemented")
            else:
                raise CodegenException("Unsupported VariableAccess parts length")
        elif isinstance(node, BinaryOp):
            self._codegen_binary_op(node, target_reg)
        elif isinstance(node, FunctionCall):
            self._codegen_function_call(node)
            if target_reg != 'rax':
                self.emit(f"mov {target_reg}, rax")
        else:
            raise CodegenException(f"Unsupported expression node type: {type(node).__name__}")

    def _codegen_binary_op(self, node, target_reg='rax'):
        self._codegen_expression(node.left, 'rax')
        self.emit("push rax")
        self._codegen_expression(node.right, 'rax')
        self.emit("mov rbx, rax")
        self.emit("pop rax")

        op_map = {
            TokenType.PLUS: ("add rax, rbx",),
            TokenType.MINUS: ("sub rax, rbx",),
            TokenType.STAR: ("imul rax, rbx",),
            TokenType.SLASH: (
                "cqo",
                "idiv rbx",
            ),
            TokenType.EQ: (
                "cmp rax, rbx",
                "sete al",
                "movzx rax, al",
            ),
            TokenType.NOT_EQ: (
                "cmp rax, rbx",
                "setne al",
                "movzx rax, al",
            ),
            TokenType.LT: (
                "cmp rax, rbx",
                "setl al",
                "movzx rax, al",
            ),
            TokenType.LE: (
                "cmp rax, rbx",
                "setle al",
                "movzx rax, al",
            ),
            TokenType.GT: (
                "cmp rax, rbx",
                "setg al",
                "movzx rax, al",
            ),
            TokenType.GE: (
                "cmp rax, rbx",
                "setge al",
                "movzx rax, al",
            ),
            TokenType.PERCENT: (
                "cqo",
                "idiv rbx",
                "mov rax, rdx",
            ),
        }

        asm_instrs = op_map.get(node.op)
        if asm_instrs is None:
            raise CodegenException(f"Unsupported binary operator {node.op}")

        for instr in asm_instrs:
            self.emit(instr)

        if target_reg != 'rax':
            self.emit(f"mov {target_reg}, rax")
