from core.parser import Parser, ImportNode
from core.lexer import Lexer
import os

class Importer:
    def __init__(self, base_path):
        self.base_path = base_path
        self.visited = set()

    def resolve_imports(self, ast_nodes):
        resolved_ast = []
        for node in ast_nodes:
            if isinstance(node, ImportNode):
                module_path = self.resolve_module_path(node.parts)
                if module_path in self.visited:
                    continue
                self.visited.add(module_path)
                module_ast = self.load_module(module_path)
                module_ast = self.resolve_imports(module_ast)
                resolved_ast.extend(module_ast)
            else:
                resolved_ast.append(node)
        return resolved_ast

    def resolve_module_path(self, parts):
        relative_path = os.path.join(*parts) + ".sw"
        full_path = os.path.join(self.base_path, relative_path)
        if not os.path.isfile(full_path):
            raise FileNotFoundError(f"Module file not found: {full_path}")
        return full_path

    def load_module(self, path):
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        parser = Parser(source)
        return parser.parse()
