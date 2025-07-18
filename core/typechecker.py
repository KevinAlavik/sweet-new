import sys
import struct

class TypeError(Exception):
    def __init__(self, msg):
        print("Typechecker Error: " + msg)
        exit(1)

class Type:
    def __init__(self, name, is_array=False, size=None):
        self.name = name
        self.is_array = is_array
        self.size = size

    def __repr__(self):
        return f"Type(name={self.name!r}, is_array={self.is_array}, size={self.size})"

    def __eq__(self, other):
        if not isinstance(other, Type):
            return False
        return (self.name == other.name and
                self.is_array == other.is_array and
                self.size == other.size)

    def is_integer(self):
        return self.name in {"u8","u16","u32","u64","i8","i16","i32","i64","usize","isize","int","uint"}

    def is_signed(self):
        return self.name in {"i8","i16","i32","i64","isize","int"}

    def is_unsigned(self):
        return self.name in {"u8","u16","u32","u64","usize","uint"}

    def is_string(self):
        return self.name == "string"
    
    def is_bool(self):
        return self.name == "bool"

    def can_have_len_property(self):
        return self.is_array

    def is_float(self):
        return self.name in {"f32", "f64"}

    def is_compatible_with(self, other):
        if self == other:
            return True
        if self.is_unsigned() and other.name == "int":
            return True
        if self.is_signed() and other.name == "uint":
            return True
        return False


class TypeChecker:
    def __init__(self):
        self.symbols = {}   # global + current scope variables
        self.functions = {}
        self.ptr_bits = struct.calcsize("P") * 8

    def error(self, msg):
        raise TypeError(msg)

    def check(self, node):
        if isinstance(node, list):
            for n in node:
                self.check(n)
            return
        method = "check_" + node.__class__.__name__
        if hasattr(self, method):
            return getattr(self, method)(node)
        else:
            self.error(f"No type checker implemented for {node.__class__.__name__}")

    def check_NumberLiteral(self, node):
        if isinstance(node.value, float):
            return Type("f64")
        else:
            return Type("int")

    def check_StringLiteral(self, node):
        return Type("string")

    def check_BooleanLiteral(self, node):
        return Type("bool")

    def check_VariableAccess(self, node):
        name = node.parts[0]
        if name not in self.symbols:
            self.error(f"Variable '{name}' not defined")
        var_type = self.symbols[name]
        if len(node.parts) > 1:
            member = node.parts[1]
            return self.check_member_access(var_type, member)
        return var_type

    def check_member_access(self, base_type, member_name):
        if member_name == "len":
            if base_type.can_have_len_property():
                return Type("usize")
            self.error(f"Type '{base_type}' has no member 'len'")
        self.error(f"Unknown member '{member_name}' on type '{base_type}'")

    def check_Assignment(self, node):
        if node.name not in self.symbols:
            self.error(f"Variable '{node.name}' not defined")
        var_type = self.symbols[node.name]
        val_type = self.check(node.value)
        if not var_type.is_compatible_with(val_type):
            self.error(f"Type mismatch in assignment to '{node.name}': expected {var_type}, got {val_type}")
        self.check_integer_range(var_type, node.value)
        return var_type

    def check_VariableDef(self, node):
        if node.name in self.symbols:
            self.error(f"Variable '{node.name}' already defined")
        val_type = self.check(node.value)
        if not node.type_.is_compatible_with(val_type):
            self.error(f"Type mismatch in variable definition '{node.name}': declared {node.type_}, got {val_type}")
        self.check_integer_range(node.type_, node.value)
        self.symbols[node.name] = node.type_
        return node.type_

    def check_BinaryOp(self, node):
        left_type = self.check(node.left)
        right_type = self.check(node.right)
        if left_type != right_type:
            self.error(f"Type mismatch in binary operation: {left_type} {node.op} {right_type}")
        if not left_type.is_integer() and not left_type.is_string() and not left_type.is_array:
            self.error(f"Unsupported operand type(s) for {node.op}: '{left_type}'")
        return left_type

    def check_FunctionCall(self, node):
        if node.name not in self.functions:
            self.error(f"Function '{node.name}' not defined")
        func_def = self.functions[node.name]
        
        if getattr(func_def, 'is_variadic', False):
            if len(node.arguments) < len(func_def.parameters):
                self.error(f"Function '{node.name}' expects at least {len(func_def.parameters)} arguments, got {len(node.arguments)}")
            for param, arg in zip(func_def.parameters, node.arguments[:len(func_def.parameters)]):
                arg_type = self.check(arg)
                if not param.type_.is_compatible_with(arg_type):
                    self.error(f"Function '{node.name}' argument '{param.name}' expects {param.type_}, got {arg_type}")
        else:
            if len(func_def.parameters) != len(node.arguments):
                self.error(f"Function '{node.name}' expects {len(func_def.parameters)} arguments, got {len(node.arguments)}")
            for param, arg in zip(func_def.parameters, node.arguments):
                arg_type = self.check(arg)
                if not param.type_.is_compatible_with(arg_type):
                    self.error(f"Function '{node.name}' argument '{param.name}' expects {param.type_}, got {arg_type}")
        return func_def.return_type

    def check_ReturnNode(self, node):
        if node.expression is None:
            return Type("void")
        return self.check(node.expression)

    def check_Parameter(self, node):
        return node.type_

    def check_ExternDecl(self, node):
        if node.name in self.functions:
            self.error(f"Function '{node.name}' already defined or declared")
        self.functions[node.name] = node
        return node.return_type
    
    def check_FunctionDef(self, node):
        if node.name in self.functions:
            self.error(f"Function '{node.name}' already defined")
        self.functions[node.name] = node
        old_symbols = self.symbols.copy()
        # Add parameters to the current scope for the function body
        for param in node.parameters:
            if param.name in self.symbols:
                self.error(f"Parameter '{param.name}' already defined in scope")
            self.symbols[param.name] = param.type_
        for stmt in node.body:
            stmt_type = self.check(stmt)
            if stmt.__class__.__name__ == "ReturnNode":
                if not node.return_type.is_compatible_with(stmt_type):
                    self.error(f"Function '{node.name}' returns {stmt_type}, but declared {node.return_type}")
        # Restore symbols (globals + prior)
        self.symbols = old_symbols
        return node.return_type
    
    def check_ArrayLiteral(self, node):
        if not node.elements:
            self.error("Empty array literals are not supported or need explicit type annotation")

        element_types = [self.check(elem) for elem in node.elements]

        first_type = element_types[0]
        for et in element_types[1:]:
            if not first_type.is_compatible_with(et):
                self.error(f"Array literal element type mismatch: {first_type} vs {et}")

        return Type(name=first_type.name, is_array=True, size=len(node.elements))
    
    def check_ImportNode(self, node):
        pass


    def check_integer_range(self, type_, value_node):
        if type_.is_float():
            if value_node.__class__.__name__ != "NumberLiteral":
                return
            val = value_node.value
            if type_.name == "f32":
                import math
                max_val = 3.4028235e+38
                min_val = -max_val
                if not (min_val <= val <= max_val) and not (math.isinf(val) or math.isnan(val)):
                    self.error(f"Float literal {val} out of range for type {type_.name}")
            elif type_.name == "f64":
                pass
            return

        if not type_.is_integer():
            return
        if value_node.__class__.__name__ != "NumberLiteral":
            return
        val = value_node.value
        if type_.name == "usize":
            max_val = (1 << self.ptr_bits) - 1
            min_val = 0
        elif type_.name == "isize":
            max_val = (1 << (self.ptr_bits - 1)) - 1
            min_val = -(1 << (self.ptr_bits - 1))
        elif type_.name.startswith("u") and type_.name[1:].isdigit():
            bits = int(type_.name[1:])
            min_val = 0
            max_val = (1 << bits) - 1
        elif type_.name.startswith("i") and type_.name[1:].isdigit():
            bits = int(type_.name[1:])
            min_val = -(1 << (bits - 1))
            max_val = (1 << (bits - 1)) - 1
        elif type_.name == "int":
            max_val = (1 << (self.ptr_bits - 1)) - 1
            min_val = -(1 << (self.ptr_bits - 1))
        elif type_.name == "uint":
            max_val = (1 << self.ptr_bits) - 1
            min_val = 0
        else:
            return
        if not (min_val <= val <= max_val):
            self.error(f"Integer literal {val} out of range for type {type_.name} (allowed: {min_val} to {max_val})")
