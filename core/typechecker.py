import sys
import struct
from dataclasses import dataclass
from typing import Optional, Dict, List, Any

class TypeError(Exception):
    def __init__(self, msg: str, node: Optional[Any] = None):
        context = f" at node {node.__class__.__name__}" if node else ""
        super().__init__(f"Typechecker Error: {msg}{context}")

@dataclass
class Type:
    name: str
    pointer_level: int = 0
    is_array: bool = False
    size: Optional[int] = None

    def __repr__(self) -> str:
        ptr_str = "*" * self.pointer_level
        arr_str = f"[{self.size}]" if self.is_array else ""
        return f"{self.name}{ptr_str}{arr_str}"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Type):
            return False
        return (self.name == other.name and
                self.is_array == other.is_array and
                self.size == other.size and
                self.pointer_level == other.pointer_level)

    def is_integer(self) -> bool:
        return self.pointer_level == 0 and self.name in {
            "u8", "u16", "u32", "u64", "i8", "i16", "i32", "i64",
            "usize", "isize", "int", "uint", "char"
        }

    def is_signed(self) -> bool:
        return self.pointer_level == 0 and self.name in {
            "i8", "i16", "i32", "i64", "isize", "int"
        }

    def is_unsigned(self) -> bool:
        return self.pointer_level == 0 and self.name in {
            "u8", "u16", "u32", "u64", "usize", "uint", "char"
        }

    def is_char(self) -> bool:
        return self.pointer_level == 0 and self.name == "char"

    def is_string(self) -> bool:
        return self.pointer_level == 0 and self.name == "string"

    def is_bool(self) -> bool:
        return self.pointer_level == 0 and self.name == "bool"

    def is_float(self) -> bool:
        return self.pointer_level == 0 and self.name in {"f32", "f64"}

    def can_have_len_property(self) -> bool:
        return self.is_array

    def is_compatible_with(self, other: 'Type') -> bool:
        if self == other:
            return True

        if (self.name == "string" and other.name == "u8" and other.pointer_level == 1) or \
           (other.name == "string" and self.name == "u8" and self.pointer_level == 1):
            return True

        if (self.name == "string" and other.name == "char" and other.pointer_level == 1) or \
           (other.name == "string" and self.name == "char" and self.pointer_level == 1):
            return True

        if self.pointer_level == 0 and other.pointer_level == 0:
            if self.is_unsigned() and other.name == "int":
                return True
            if self.is_signed() and other.name == "uint":
                return True
            if self.is_char() and other.name in {"u8", "i8"}:
                return True
            if other.is_char() and self.name in {"u8", "i8"}:
                return True

        if self.pointer_level > 0 or other.pointer_level > 0:
            if self.pointer_level == other.pointer_level:
                if self.name == other.name or self.name == "void" or other.name == "void":
                    return True
                if self.name == "char" or other.name == "char":
                    return True

        return False

class TypeChecker:
    def __init__(self):
        self.symbols: Dict[str, Type] = {}
        self.functions: Dict[str, Any] = {}
        self.ptr_bits: int = struct.calcsize("P") * 8
        self._current_function: Optional[str] = None

    def check(self, node: Any) -> Type:
        if isinstance(node, list):
            result_type = Type("void")
            for n in node:
                result_type = self.check(n)
            return result_type

        method_name = f"check_{node.__class__.__name__}"
        method = getattr(self, method_name, None)
        if method:
            return method(node)
        raise TypeError(f"No type checker implemented for {node.__class__.__name__}", node)

    def check_NumberLiteral(self, node: Any) -> Type:
        return Type("f64" if isinstance(node.value, float) else "int")

    def check_StringLiteral(self, node: Any) -> Type:
        return Type("string")

    def check_CharLiteral(self, node: Any) -> Type:
        return Type("char")

    def check_BooleanLiteral(self, node: Any) -> Type:
        return Type("bool")

    def check_VariableAccess(self, node: Any) -> Type:
        name = node.parts[0]
        if name not in self.symbols:
            raise TypeError(f"Variable '{name}' not defined", node)
        
        var_type = self.symbols[name]
        if len(node.parts) > 1:
            return self._check_member_access(var_type, node.parts[1], node)
        return var_type

    def _check_member_access(self, base_type: Type, member_name: str, node: Any) -> Type:
        if member_name == "len":
            if base_type.can_have_len_property():
                return Type("usize")
            raise TypeError(f"Type '{base_type}' has no member 'len'", node)
        raise TypeError(f"Unknown member '{member_name}' on type '{base_type}'", node)

    def check_Assignment(self, node: Any) -> Type:
        if isinstance(node.name, str):
            if node.name not in self.symbols:
                raise TypeError(f"Variable '{node.name}' not defined", node)
            var_type = self.symbols[node.name]
        else:
            var_type = self.check(node.name)

        val_type = self.check(node.value)
        if not var_type.is_compatible_with(val_type):
            raise TypeError(f"Type mismatch in assignment to '{node.name}': expected {var_type}, got {val_type}", node)
        
        self._check_integer_range(var_type, node.value, node)
        return var_type

    def check_VariableDef(self, node: Any) -> Type:
        if node.name in self.symbols:
            raise TypeError(f"Variable '{node.name}' already defined", node)
        
        val_type = self.check(node.value)
        if not node.type_.is_compatible_with(val_type):
            raise TypeError(f"Type mismatch in variable definition '{node.name}': declared {node.type_}, got {val_type}", node)
        
        self._check_integer_range(node.type_, node.value, node)
        self.symbols[node.name] = node.type_
        return node.type_

    def check_BinaryOp(self, node: Any) -> Type:
        left_type = self.check(node.left)
        right_type = self.check(node.right)
        
        if left_type != right_type:
            raise TypeError(f"Type mismatch in binary operation: {left_type} {node.op} {right_type}", node)
        
        if not (left_type.is_integer() or left_type.is_string() or left_type.is_array):
            raise TypeError(f"Unsupported operand type(s) for {node.op}: '{left_type}'", node)
        
        return left_type

    def check_FunctionCall(self, node: Any) -> Type:
        if node.name not in self.functions:
            raise TypeError(f"Function '{node.name}' not defined", node)
        
        func_def = self.functions[node.name]
        
        if getattr(func_def, 'is_variadic', False):
            if len(node.arguments) < len(func_def.parameters):
                raise TypeError(f"Function '{node.name}' expects at least {len(func_def.parameters)} arguments, got {len(node.arguments)}", node)
            for param, arg in zip(func_def.parameters, node.arguments[:len(func_def.parameters)]):
                arg_type = self.check(arg)
                if not param.type_.is_compatible_with(arg_type):
                    raise TypeError(f"Function '{node.name}' argument '{param.name}' expects {param.type_}, got {arg_type}", node)
        else:
            if len(func_def.parameters) != len(node.arguments):
                raise TypeError(f"Function '{node.name}' expects {len(func_def.parameters)} arguments, got {len(node.arguments)}", node)
            for param, arg in zip(func_def.parameters, node.arguments):
                arg_type = self.check(arg)
                if not param.type_.is_compatible_with(arg_type):
                    raise TypeError(f"Function '{node.name}' argument '{param.name}' expects {param.type_}, got {arg_type}", node)
        
        return func_def.return_type

    def check_ReturnNode(self, node: Any) -> Type:
        if node.expression is None:
            return Type("void")
        return_type = self.check(node.expression)
        if self._current_function and not self.functions[self._current_function].return_type.is_compatible_with(return_type):
            raise TypeError(f"Function '{self._current_function}' returns {return_type}, but declared {self.functions[self._current_function].return_type}", node)
        return return_type

    def check_Parameter(self, node: Any) -> Type:
        return node.type

    def check_ExternDecl(self, node: Any) -> Type:
        if node.var:
            if node.name in self.symbols:
                raise TypeError(f"Extern variable '{node.name}' already defined", node)
            self.symbols[node.name] = node.return_type
        else:
            if node.name in self.functions:
                raise TypeError(f"Function '{node.name}' already defined or declared", node)
            self.functions[node.name] = node
        return node.return_type

    def check_FunctionDef(self, node: Any) -> Type:
        if node.name in self.functions:
            raise TypeError(f"Function '{node.name}' already defined", node)
        
        self.functions[node.name] = node
        self._current_function = node.name
        old_symbols = self.symbols.copy()
        
        for param in node.parameters:
            if param.name in self.symbols:
                raise TypeError(f"Parameter '{param.name}' already defined in scope", node)
            self.symbols[param.name] = param.type_
        
        for stmt in node.body:
            self.check(stmt)
        
        self.symbols = old_symbols
        self._current_function = None
        return node.return_type

    def check_ArrayLiteral(self, node: Any) -> Type:
        if not node.elements:
            raise TypeError("Empty array literals are not supported or need explicit type annotation", node)
        
        element_types = [self.check(elem) for elem in node.elements]
        first_type = element_types[0]
        
        for et in element_types[1:]:
            if not first_type.is_compatible_with(et):
                raise TypeError(f"Array literal element type mismatch: {first_type} vs {et}", node)
        
        return Type(name=first_type.name, is_array=True, size=len(node.elements))

    def check_ImportNode(self, node: Any) -> Type:
        return Type("void")

    def check_AsmBlock(self, node: Any) -> Type:
        return Type("void")

    def check_PointerLiteral(self, node: Any) -> Type:
        if isinstance(node.address, int):
            return Type("void", pointer_level=1)
        
        addr_type = self.check(node.address)
        return Type(addr_type.name, pointer_level=addr_type.pointer_level + 1)

    def check_Dereference(self, node: Any) -> Type:
        var_type = self.check(node.expr)
        
        if var_type.pointer_level == 0:
            raise TypeError(f"Cannot dereference non-pointer type {var_type}", node)
        
        if var_type.pointer_level == 1 and var_type.name == "void":
            raise TypeError("Cannot dereference pointer to void", node)
        
        return Type(name=var_type.name, pointer_level=var_type.pointer_level - 1)

    def check_Cast(self, node: Any) -> Type:
        self.check(node.expr)
        return node.target_type

    def _check_integer_range(self, type_: Type, value_node: Any, node: Any) -> None:
        if type_.is_float():
            if value_node.__class__.__name__ != "NumberLiteral":
                return
            val = value_node.value
            if type_.name == "f32":
                import math
                max_val = 3.4028235e+38
                min_val = -max_val
                if not (min_val <= val <= max_val) and not (math.isinf(val) or math.isnan(val)):
                    raise TypeError(f"Float literal {val} out of range for type {type_.name}", node)
            return

        if not type_.is_integer() or value_node.__class__.__name__ not in {"NumberLiteral", "CharLiteral"}:
            return
        
        if value_node.__class__.__name__ == "CharLiteral":
            val = ord(value_node.value)
        else:
            val = value_node.value

        if type_.name == "usize":
            min_val, max_val = 0, (1 << self.ptr_bits) - 1
        elif type_.name == "isize":
            min_val, max_val = -(1 << (self.ptr_bits - 1)), (1 << (self.ptr_bits - 1)) - 1
        elif type_.name.startswith("u") and type_.name[1:].isdigit():
            bits = int(type_.name[1:])
            min_val, max_val = 0, (1 << bits) - 1
        elif type_.name.startswith("i") and type_.name[1:].isdigit():
            bits = int(type_.name[1:])
            min_val, max_val = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
        elif type_.name == "int":
            min_val, max_val = -(1 << (self.ptr_bits - 1)), (1 << (self.ptr_bits - 1)) - 1
        elif type_.name == "uint":
            min_val, max_val = 0, (1 << self.ptr_bits) - 1
        elif type_.name == "char":
            min_val, max_val = 0, 255
        else:
            return

        if not (min_val <= val <= max_val):
            raise TypeError(f"Integer literal {val} out of range for type {type_.name} (allowed: {min_val} to {max_val})", node)