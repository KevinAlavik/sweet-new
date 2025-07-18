from abc import ABC
from core.lexer import Lexer, Token, TokenType
from core.typechecker import Type

# === AST Nodes ===
class ASTNode(ABC):
    def __repr__(self):
        return str(self)

class NumberLiteral(ASTNode):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return f"Number({self.value})"
    
class BooleanLiteral(ASTNode):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return f"BooleanLiteral({self.value})"

class StringLiteral(ASTNode):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return f"String({repr(self.value)})"

class ArrayLiteral(ASTNode):
    def __init__(self, elements):
        self.elements = elements

    def __str__(self):
        elements_str = ", ".join(str(elem) for elem in self.elements)
        return f"ArrayLiteral([{elements_str}])"
    
class PointerLiteral(ASTNode):
    def __init__(self, address: int):
        self.address = address

    def __str__(self):
        if isinstance(self.address, int):
            return f"PointerLiteral(0x{hex(self.address)})"
        else:
            return f"PointerLiteral({str(self.address)})"

class BinaryOp(ASTNode):
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

    def __str__(self):
        return f"BinaryOp({self.left}, {self.op.name}, {self.right})"

class ImportNode(ASTNode):
    def __init__(self, parts, imported_symbols=None):
        self.parts = parts
        self.imported_symbols = imported_symbols

    def __str__(self):
        if self.imported_symbols:
            return f"Import({'.'.join(self.parts)}: {', '.join(self.imported_symbols)})"
        else:
            return f"Import({'.'.join(self.parts)})"

class FunctionCall(ASTNode):
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments

    def __str__(self):
        args = ", ".join(str(arg) for arg in self.arguments)
        return f"FunctionCall({self.name}, [{args}])"

class VariableAccess(ASTNode):
    def __init__(self, parts):
        self.parts = parts

    def __str__(self):
        result = ""
        for p in self.parts:
            if isinstance(p, str):
                if result:
                    result += "."
                result += p
            else:
                result += f"[{p}]"
        return f"VariableAccess({result})"

class ReturnNode(ASTNode):
    def __init__(self, expression=None):
        self.expression = expression

    def __str__(self):
        if self.expression is None:
            return "Return()"
        return f"Return({self.expression})"

class Parameter(ASTNode):
    def __init__(self, name, type_):
        self.name = name
        self.type_ = type_

    def __str__(self):
        return f"Parameter({self.name}, {self.type_})"

class FunctionDef(ASTNode):
    def __init__(self, name, parameters, return_type, body, is_public=False):
        self.name = name
        self.parameters = parameters
        self.return_type = return_type
        self.body = body
        self.is_public = is_public

    def __str__(self):
        params = ", ".join(str(param) for param in self.parameters)
        return f"{'Public' if self.is_public else 'Private'}FunctionDef({self.name}({params}), {self.return_type}, {self.body})"

class VariableDef(ASTNode):
    def __init__(self, name, type_, value, is_public=False):
        self.name = name
        self.type_ = type_
        self.value = value
        self.is_public = is_public

    def __str__(self):
        return f"{'Public' if self.is_public else 'Private'}VariableDef({self.name}, {self.type_}, {self.value})"

class Assignment(ASTNode):
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __str__(self):
        return f"Assignment({self.name}, {self.value})"
    
class ExternDecl(ASTNode):
    def __init__(self, name, is_variadic, return_type, parameters=None, is_var=False):
        self.name = name
        self.is_variadic = is_variadic
        self.return_type = return_type or Type("void")
        self.parameters = parameters if parameters is not None else []
        self.var = is_var
    def __str__(self):
        return f"ExternDecl({self.name}, variadic={self.is_variadic}, return_type={self.return_type}, parameters={self.parameters}, var={self.var})"

class AsmBlock(ASTNode):
    def __init__(self, instructions: list[str]):
        self.instructions = instructions

    def __str__(self):
        return f"AsmBlock({self.instructions})"

class Dereference(ASTNode):
    def __init__(self, expr):
        self.expr = expr

    def __str__(self):
        return f"Dereference({self.expr})"
    
class Cast(ASTNode):
    def __init__(self, expr, target_type):
        self.expr = expr
        self.target_type = target_type

    def __str__(self):
        return f"Cast({self.expr} as {self.target_type})"

# === Parser ===
class Parser:
    def __init__(self, src):
        self.lexer = Lexer(src)
        self.src = src
        self.tokens = self.lexer.scan_tokens()
        self.current_index = 0
        self.current_token = self.tokens[self.current_index]

    class ParserError(SyntaxError):
        def __init__(self, message, line, column, source_lines):
            column = column - 1
            super().__init__(f"Line {line}, Col {column}: {message}")
            self.message = message
            self.line = line
            self.column = column
            self.source_lines = source_lines

        def display(self):
            print(f"ParserError: {self.message} at line {self.line}, column {self.column}")
            if 1 <= self.line <= len(self.source_lines):
                source_line = self.source_lines[self.line - 1]
                print(source_line.rstrip('\n'))
                pointer_line = ' ' * (self.column - 1) + '^'
                print(pointer_line)
            else:
                print("(Source line unavailable)")

    def eat(self):
        token = self.current_token
        self.current_index += 1
        if self.current_index < len(self.tokens):
            self.current_token = self.tokens[self.current_index]
        else:
            self.current_token = Token(TokenType.EOF, None, -1, -1)
        return token

    def expect(self, type_):
        if self.current_token.type == type_:
            return self.eat()
        else:
            raise self.ParserError(
                f"Expected {type_}, got {self.current_token.type}",
                self.current_token.line,
                self.current_token.column,
                self.src.splitlines()
            )
    
    def parse_type(self):
        type_name = self.expect(TokenType.IDENT).value
        pointer_level = 0
        while self.current_token.type == TokenType.STAR:
            self.eat()
            pointer_level += 1

        is_array = False
        size = None
        if self.current_token.type == TokenType.LBRACKET:
            self.eat()
            if self.current_token.type == TokenType.NLIT:
                size = int(self.eat().value)
                self.expect(TokenType.RBRACKET)
            else:
                self.expect(TokenType.RBRACKET)
            is_array = True

        return Type(type_name, pointer_level=pointer_level, is_array=is_array, size=size)

    def parse_dotted_identifier(self):
        parts = [self.expect(TokenType.IDENT).value]
        while self.current_token.type == TokenType.DOT:
            self.eat()
            parts.append(self.expect(TokenType.IDENT).value)
        return parts

    def parse_import(self):
        self.expect(TokenType.KEYWORD)
        parts = self.parse_dotted_identifier()

        imported_symbols = None
        if self.current_token.type == TokenType.COLON:
            self.eat()
            imported_symbols = []
            while True:
                imported_symbols.append(self.expect(TokenType.IDENT).value)
                if self.current_token.type != TokenType.COMMA:
                    break
                self.eat()
        self.expect(TokenType.SEMICOLON)

        return ImportNode(parts, imported_symbols)


    def parse_arguments(self):
        arguments = []
        if self.current_token.type != TokenType.RPAREN:
            while True:
                arguments.append(self.parse_expression())
                if self.current_token.type != TokenType.COMMA:
                    break
                self.eat()
        self.expect(TokenType.RPAREN)
        return arguments

    def parse_parameters(self):
        parameters = []
        if self.current_token.type != TokenType.RPAREN:
            while True:
                param_name = self.expect(TokenType.IDENT).value
                self.expect(TokenType.COLON)
                param_type = self.parse_type()
                parameters.append(Parameter(param_name, param_type))
                if self.current_token.type != TokenType.COMMA:
                    break
                self.eat()
        self.expect(TokenType.RPAREN)
        return parameters

    def parse_variable_access_with_indexing(self):
        parts = [self.expect(TokenType.IDENT).value]

        while True:
            if self.current_token.type == TokenType.DOT:
                self.eat()
                parts.append(self.expect(TokenType.IDENT).value)
            elif self.current_token.type == TokenType.LBRACKET:
                self.eat()
                index_expr = self.parse_expression()
                self.expect(TokenType.RBRACKET)
                parts.append(index_expr)
            else:
                break
        return VariableAccess(parts)

    def parse_primary(self):
        tok = self.current_token
        if tok.type == TokenType.NLIT or tok.type == TokenType.FLIT:
            self.eat()
            return NumberLiteral(tok.value)
        elif tok.type == TokenType.SLIT:
            self.eat()
            return StringLiteral(tok.value)
        elif tok.type == TokenType.BLIT:
            self.eat()
            return BooleanLiteral(tok.value)
        elif tok.type == TokenType.KEYWORD and tok.value == "null":
            self.eat()
            return PointerLiteral(0)
        elif tok.type == TokenType.LBRACKET:
            self.eat()
            elements = []
            if self.current_token.type != TokenType.RBRACKET:
                while True:
                    elements.append(self.parse_expression())
                    if self.current_token.type != TokenType.COMMA:
                        break
                    self.eat()
            self.expect(TokenType.RBRACKET)
            return ArrayLiteral(elements)
        elif tok.type == TokenType.STAR:
            deref_level = 1
            self.eat()
            while self.current_token.type == TokenType.STAR:
                self.eat()
                deref_level += 1
            
            var_access = self.parse_variable_access_with_indexing()
            if self.current_token.type == TokenType.LPAREN:
                raise self.ParserError(
                        "Attempt to deref function call",
                        self.current_token.line,
                        self.current_token.column,
                        self.src.splitlines()
                    )
            elif self.current_token.type == TokenType.ASSIGN:
                self.eat()
                value = self.parse_expression()
                node = var_access
                for _ in range(deref_level):
                    node = Dereference(node)

                if len(var_access.parts) == 1 and isinstance(var_access.parts[0], str):
                    return Assignment(node, value)
                else:
                    raise self.ParserError(
                        "Assignment to indexed variables not supported yet",
                        self.current_token.line,
                        self.current_token.column,
                        self.src.splitlines()
                    )
            else:
                node = var_access
                for _ in range(deref_level):
                    node = Dereference(node)
                return node

        elif tok.type == TokenType.IDENT:
            var_access = self.parse_variable_access_with_indexing()
            if self.current_token.type == TokenType.LPAREN:
                self.eat()
                arguments = self.parse_arguments()
                return FunctionCall(var_access.parts[0], arguments)
            elif self.current_token.type == TokenType.ASSIGN:
                self.eat()
                value = self.parse_expression()
                if len(var_access.parts) == 1 and isinstance(var_access.parts[0], str):
                    return Assignment(var_access.parts[0], value)
                else:
                    raise self.ParserError(
                        "Assignment to indexed variables not supported yet",
                        self.current_token.line,
                        self.current_token.column,
                        self.src.splitlines()
                    )
            else:
                return var_access
        elif tok.type == TokenType.LPAREN:
            self.eat()
            expr = self.parse_expression()
            self.expect(TokenType.RPAREN)
            return expr
        else:
            raise self.ParserError(
                f"Unexpected token: {tok.type}",
                tok.line,
                tok.column,
                self.src.splitlines()
            )

    def parse_unary(self):
        if self.current_token.type == TokenType.MINUS:
            self.eat()
            operand = self.parse_unary()
            if isinstance(operand, NumberLiteral):
                return NumberLiteral(-operand.value)
            else:
                return BinaryOp(NumberLiteral(0), TokenType.MINUS, operand)
        elif self.current_token.type == TokenType.AND:
            self.eat()
            expr = self.parse_unary()
            return PointerLiteral(expr)

        expr = self.parse_primary()

        while self.current_token.type == TokenType.KEYWORD and self.current_token.value == "as":
            self.eat()
            target_type = self.parse_type()
            expr = Cast(expr, target_type)

        return expr


    def parse_expression(self, precedence=0):
        PRECEDENCE = {
            TokenType.OR_OR: 1,
            TokenType.OR: 2,
            TokenType.XOR: 3,
            TokenType.AND_AND: 4,
            TokenType.AND: 5,
            TokenType.EQ: 6,
            TokenType.NE: 6,
            TokenType.LT: 7,
            TokenType.GT: 7,
            TokenType.LE: 7,
            TokenType.GE: 7,
            TokenType.PLUS: 8,
            TokenType.MINUS: 8,
            TokenType.STAR: 9,
            TokenType.SLASH: 9,
            TokenType.PERCENT: 9,
        }

        left = self.parse_unary()

        while True:
            tok = self.current_token
            if tok.type not in PRECEDENCE:
                break
            token_prec = PRECEDENCE[tok.type]
            if token_prec < precedence:
                break
            self.eat()
            right = self.parse_expression(token_prec + 1)
            left = BinaryOp(left, tok.type, right)

        return left

    def parse_statement(self):
        if self.current_token.type == TokenType.KEYWORD:
            kw = self.current_token.value
            if kw == "import":
                return self.parse_import()
            elif kw == "return":
                self.eat()
                if self.current_token.type != TokenType.SEMICOLON:
                    expr = self.parse_expression()
                    self.expect(TokenType.SEMICOLON)
                    return ReturnNode(expr)
                else:
                    self.expect(TokenType.SEMICOLON)
                    return ReturnNode()
            elif kw == "pub":
                self.eat()
                if self.current_token.type == TokenType.KEYWORD and self.current_token.value == "fn":
                    return self.parse_function(is_public=True)
                else:
                    return self.parse_variable(is_public=True)
            elif kw == "fn":
                return self.parse_function(is_public=False)
            elif kw == "var":
                return self.parse_variable(is_public=False)
            elif kw == "extern":
                return self.parse_extern()
            elif kw == "asm":
                return self.parse_asm_block()
            else:
                expr = self.parse_expression()
                self.expect(TokenType.SEMICOLON)
                return expr
        else:
            expr = self.parse_expression()
            self.expect(TokenType.SEMICOLON)
            return expr

    def parse_function(self, is_public):
        self.expect(TokenType.KEYWORD)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.LPAREN)
        parameters = self.parse_parameters()
        return_type = None
        if self.current_token.type == TokenType.ARROW:
            self.eat()
            return_type = self.parse_type()
        self.expect(TokenType.LBRACE)
        body = []
        while self.current_token.type != TokenType.RBRACE:
            body.append(self.parse_statement())
        self.expect(TokenType.RBRACE)
        return FunctionDef(name, parameters, return_type, body, is_public)

    def parse_variable(self, is_public):
        self.expect(TokenType.KEYWORD)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.COLON)
        type_ = self.parse_type()
        value = None
        if self.current_token.type == TokenType.ASSIGN:
            self.eat()
            value = self.parse_expression()
        self.expect(TokenType.SEMICOLON)
        return VariableDef(name, type_, value, is_public)

    def parse_extern(self):
        self.expect(TokenType.KEYWORD)
        name = self.expect(TokenType.IDENT).value
        is_variadic = False
        parameters = []
        return_type = None

        if self.current_token.type == TokenType.LPAREN:
            self.eat()
            if self.current_token.type != TokenType.RPAREN:
                while True:
                    if self.current_token.type == TokenType.DOTS:
                        is_variadic = True
                        self.eat()
                        break
                    param_type = self.parse_type()
                    parameters.append(param_type)
                    if self.current_token.type != TokenType.COMMA:
                        break
                    self.eat()
            self.expect(TokenType.RPAREN)

        if self.current_token.type == TokenType.ARROW:
            self.eat()
            return_type = self.parse_type()
        self.expect(TokenType.SEMICOLON)

        return ExternDecl(name, is_variadic, return_type, parameters)
    
    def parse_asm_block(self):
        self.expect(TokenType.KEYWORD)
        self.expect(TokenType.LBRACE)

        instructions = []
        current_line_tokens = []

        while self.current_token.type != TokenType.RBRACE:
            if self.current_token.type == TokenType.EOF:
                raise Exception("Unexpected EOF in asm block")

            tok = self.eat()
            if tok.value == ';':
                line = ' '.join(str(tok) for tok in current_line_tokens).strip()
                if line:
                    instructions.append(line)
                current_line_tokens = []
            else:
                current_line_tokens.append(tok.value)

        if current_line_tokens:
            line = ' '.join(str(tok) for tok in current_line_tokens).strip()
            if line:
                instructions.append(line)

        self.expect(TokenType.RBRACE)
        return AsmBlock(instructions)
    
    def parse_assignment(self):
        left = self.parse_unary()

        if self.current_token.type == TokenType.ASSIGN:
            self.eat()
            value = self.parse_expression()
            if isinstance(left, VariableAccess):
                if len(left.parts) == 1 and isinstance(left.parts[0], str):
                    return Assignment(left.parts[0], value)
                else:
                    raise self.ParserError(
                        "Assignment to indexed variables not supported yet",
                        self.current_token.line,
                        self.current_token.column,
                        self.src.splitlines()
                    )
            else:
                raise self.ParserError(
                    "Invalid assignment target",
                    self.current_token.line,
                    self.current_token.column,
                    self.src.splitlines()
                )
        else:
            return self.parse_expression()

    def parse(self):
        statements = []
        while self.current_token.type != TokenType.EOF:
            statements.append(self.parse_statement())
        return statements
