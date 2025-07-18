from enum import Enum, auto

class TokenType(Enum):
    # Literals
    NLIT = auto()    # Number literal:  42, 0, 12345
    FLIT = auto()    # Float literal:   3.14
    CLIT = auto()    # Char literal:    'a', '\n'
    SLIT = auto()    # String literal:  "hello"
    BLIT = auto()    # Boolean literal: true, false
    IDENT = auto()   # Identifier:      myVar
    KEYWORD = auto() # Keywords:        let, if, return, ...

    # Operators and symbols
    PLUS = auto()        # +
    MINUS = auto()       # -
    STAR = auto()        # *
    SLASH = auto()       # /
    PERCENT = auto()     # %
    ASSIGN = auto()      # =
    EQ = auto()          # ==
    NE = auto()          # !=
    LT = auto()          # <
    GT = auto()          # >
    LE = auto()          # <=
    GE = auto()          # >=
    ARROW = auto()       # ->
    NOT = auto()         # !
    AND = auto()         # &
    OR = auto()          # |
    XOR = auto()         # ^
    AND_AND = auto()     # &&
    OR_OR = auto()       # ||
    NOT_EQ = auto()      # !=
    XOR_ASSIGN = auto()  # ^=
    AND_ASSIGN = auto()  # &=
    OR_ASSIGN = auto()   # |=
    DOT = auto()         # .
    SEMICOLON = auto()   # ;
    COLON = auto()       # :
    LPAREN = auto()      # (
    RPAREN = auto()      # )
    LBRACKET = auto()    # [
    RBRACKET = auto()    # ]
    LBRACE = auto()      # {
    RBRACE = auto()      # }
    COMMA = auto()       # ,
    DOTS = auto()        # ...

    # Special
    EOF = auto()         # End of input

class Token:
    def __init__(self, type_, value, line, column):
        self.type = type_
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type.name}, {repr(self.value)}, line={self.line}, col={self.column})"


class LexerError(SyntaxError):
    def __init__(self, message, line, column, source_lines):
        super().__init__(f"Line {line}, Col {column}: {message}")
        self.message = message
        self.line = line
        self.column = column
        self.source_lines = source_lines

    def display(self):
        print(f"LexerError: {self.message} at line {self.line}, column {self.column}")
        if 1 <= self.line <= len(self.source_lines):
            source_line = self.source_lines[self.line - 1]
            print(source_line.rstrip('\n'))
            expanded_line = source_line.expandtabs()
            pointer_line = ' ' * (self.column - 1) + '^'
            print(pointer_line)
        else:
            print("(Source line unavailable)")


class Lexer:
    def __init__(self, src):
        self.source = src
        self.lines = src.splitlines()
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens = []

        self.keywords = {
            "let", "if", "else", "while", "return", "fn", "const", "var", "import", "extern"
        }

        self.symbols = {
            '->': TokenType.ARROW,
            '==': TokenType.EQ,
            '!=': TokenType.NE,
            '<=': TokenType.LE,
            '>=': TokenType.GE,
            '=': TokenType.ASSIGN,
            '+': TokenType.PLUS,
            '-': TokenType.MINUS,
            '*': TokenType.STAR,
            '/': TokenType.SLASH,
            '%': TokenType.PERCENT,
            '<': TokenType.LT,
            '>': TokenType.GT,
            '!': TokenType.NOT,
            '&': TokenType.AND,
            '|': TokenType.OR,
            '^': TokenType.XOR,
            '&&': TokenType.AND_AND,
            '||': TokenType.OR_OR,
            '^=': TokenType.XOR_ASSIGN,
            '&=': TokenType.AND_ASSIGN,
            '|=': TokenType.OR_ASSIGN,
            '.': TokenType.DOT,
            ';': TokenType.SEMICOLON,
            ':': TokenType.COLON,
            '(': TokenType.LPAREN,
            ')': TokenType.RPAREN,
            '[': TokenType.LBRACKET,
            ']': TokenType.RBRACKET,
            '{': TokenType.LBRACE,
            '}': TokenType.RBRACE,
            ',': TokenType.COMMA,
            '...': TokenType.DOTS
        }

    def peek(self, offset=0):
        if self.pos + offset >= len(self.source):
            return '\0'
        return self.source[self.pos + offset]

    def advance(self):
        if self.pos >= len(self.source):
            return '\0'
        c = self.source[self.pos]
        self.pos += 1
        if c == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return c

    def match(self, expected):
        if self.peek() == expected:
            self.advance()
            return True
        return False

    def add_token(self, type_, value=None):
        self.tokens.append(Token(type_, value, self.line, self.column))

    def scan_tokens(self):
        while self.pos < len(self.source):
            c = self.peek()
            if c.isspace():
                self.advance()
            elif c == '/':
                self.advance()
                if self.peek() == '/':
                    self.advance()
                    self.skip_line_comment()
                elif self.peek() == '*':
                    self.advance()
                    self.skip_block_comment()
                else:
                    self.add_token(TokenType.SLASH)
            elif c.isalpha() or c == '_':
                self.identifier()
            elif c.isdigit():
                self.number()
            elif c == '"':
                self.string()
            elif c == "'":
                self.char()
            else:
                self.match_symbol()
        self.add_token(TokenType.EOF)
        return self.tokens

    def skip_line_comment(self):
        while self.peek() != '\n' and self.peek() != '\0':
            self.advance()

    def skip_block_comment(self):
        while True:
            if self.peek() == '\0':
                raise LexerError("Unterminated block comment", self.line, self.column, self.lines)
            if self.peek() == '*' and self.peek(1) == '/':
                self.advance()
                self.advance()
                break
            self.advance()

    def match_symbol(self):
        for length in (3, 2, 1):
            if self.pos + length <= len(self.source): 
                fragment = self.source[self.pos:self.pos+length]
                if fragment in self.symbols:
                    for _ in range(length):
                        self.advance()
                    self.add_token(self.symbols[fragment], fragment)
                    return
        c = self.peek()
        raise LexerError(f"Unknown symbol '{c}'", self.line, self.column, self.lines)

    def string(self):
        start_line = self.line
        start_col = self.column
        self.advance()
        start = self.pos
        while self.peek() != '"' and self.peek() != '\0':
            if self.peek() == '\n':
                self.line += 1
                self.column = 0
            self.advance()
        if self.peek() != '"':
            raise LexerError("Unterminated string literal", start_line, start_col, self.lines)
        value = self.source[start:self.pos]
        self.advance()
        self.add_token(TokenType.SLIT, value)

    def char(self):
        start_line = self.line
        start_col = self.column
        self.advance()
        if self.peek() == '\\':
            self.advance()
            esc = self.advance()
            value = '\\' + esc
        else:
            value = self.advance()
        if self.peek() != "'":
            raise LexerError("Unterminated char literal", start_line, start_col, self.lines)
        self.advance()
        self.add_token(TokenType.CLIT, value)

    def number(self):
        start = self.pos
        start_col = self.column
        while self.peek().isdigit():
            self.advance()
        if self.peek() == '.' and self.peek(1).isdigit():
            self.advance()
            while self.peek().isdigit():
                self.advance()
            try:
                value = float(self.source[start:self.pos])
            except ValueError:
                raise LexerError("Invalid float literal", self.line, start_col, self.lines)
            self.add_token(TokenType.FLIT, value)
        else:
            try:
                value = int(self.source[start:self.pos])
            except ValueError:
                raise LexerError("Invalid integer literal", self.line, start_col, self.lines)
            self.add_token(TokenType.NLIT, value)

    def identifier(self):
        start = self.pos
        while self.peek().isalnum() or self.peek() == '_':
            self.advance()
        value = self.source[start:self.pos]
        if value in self.keywords:
            self.add_token(TokenType.KEYWORD, value)
        elif value == "true":
            self.add_token(TokenType.BLIT, True)
        elif value == "false":
            self.add_token(TokenType.BLIT, False)
        else:
            self.add_token(TokenType.IDENT, value)
