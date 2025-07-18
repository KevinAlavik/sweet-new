from core.parser import Parser, ImportNode, ExternDecl
from core.lexer import Lexer
import os

class Importer:
    def __init__(self, base_path):
        self.base_path = base_path
        self.visited = set()
        self.imported_modules = []

    def resolve_imports(self, ast_nodes):
        resolved_ast = []
        for node in ast_nodes:
            if isinstance(node, ImportNode):
                module_path = self.resolve_module_path(node.parts)
                if module_path in self.visited:
                    continue
                self.visited.add(module_path)
                self.imported_modules.append(module_path)

                module_ast = self.load_module(module_path)
                module_ast, _ = self.resolve_imports(module_ast)

                dep_graph = self.build_dependency_graph(module_ast)

                if node.imported_symbols is not None:
                    needed_symbols = self.collect_dependencies(node.imported_symbols, dep_graph)
                else:
                    needed_symbols = {item.name for item in module_ast if hasattr(item, "name")}

                for sym in needed_symbols:
                    original_node = next((item for item in module_ast if getattr(item, "name", None) == sym), None)
                    if original_node is None:
                        continue

                    extern_node = self.make_extern_node(original_node)
                    if extern_node:
                        resolved_ast.append(extern_node)

            else:
                resolved_ast.append(node)

        return resolved_ast, self.imported_modules

    def make_extern_node(self, node):
        from core.typechecker import Type

        if node.__class__.__name__ == "FunctionDef":
            is_variadic = any(getattr(param, "is_variadic", False) for param in node.parameters)
            return_type = node.return_type if node.return_type else Type("void")
            params = node.parameters if node.parameters else []
            return ExternDecl(
                name=node.name,
                is_variadic=is_variadic,
                return_type=return_type,
                parameters=params
            )
        elif node.__class__.__name__ == "VariableDef":
            return ExternDecl(
                name=node.name,
                is_variadic=False,
                return_type=node.type_,
                parameters=[]
            )
        else:
            return None

    def build_dependency_graph(self, ast_nodes):
        dep_graph = {}
        for node in ast_nodes:
            if hasattr(node, 'name'):
                deps = self.find_dependencies_in_node(node)
                dep_graph[node.name] = deps
        return dep_graph

    def collect_dependencies(self, symbols, dep_graph):
        result = set()
        stack = list(symbols)
        while stack:
            sym = stack.pop()
            if sym not in result:
                result.add(sym)
                if sym in dep_graph:
                    stack.extend(dep_graph[sym] - result)
        return result

    def find_dependencies_in_node(self, node):
        deps = set()
        def visit(n):
            if hasattr(n, 'children'):
                for c in n.children:
                    visit(c)
            if hasattr(n, 'name') and hasattr(n, 'node_type'):
                if n.node_type == 'Call':
                    deps.add(n.name)
                if hasattr(n, 'body'):
                    if isinstance(n.body, list):
                        for b in n.body:
                            visit(b)
                    else:
                        visit(n.body)
        visit(node)
        return deps

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
