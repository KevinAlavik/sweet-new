#!/bin/env python3
import argparse
import os
import subprocess
import sys
import tempfile
from typing import List, Optional
from core.parser import Parser
from core.typechecker import TypeChecker, TypeError
from core.codegen import CodeGen
from core.importer import Importer

class Compiler:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.build_dir: Optional[str] = None
        self.tempdir = None

    def setup_build_directory(self) -> None:
        if not self.args.no_clean:
            self.tempdir = tempfile.TemporaryDirectory()
            self.build_dir = self.tempdir.name
        else:
            self.build_dir = "build"
            os.makedirs(self.build_dir, exist_ok=True)

    def validate_input_files(self) -> None:
        if not os.path.exists(self.args.source):
            raise FileNotFoundError(f"Source file not found: {self.args.source}")
        if not os.path.exists(self.args.runtime):
            raise FileNotFoundError(f"Runtime file not found: {self.args.runtime}")

    def read_source(self, source_path: str) -> str:
        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                return f.read()
        except IOError as e:
            raise IOError(f"Failed to read file {source_path}: {e}")

    def process_non_binary_output(self, source: str) -> None:
        parser = Parser(source)
        try:
            ast = parser.parse()
            tokens = parser.tokens
            importer = Importer("lib/")
            ast, _ = importer.resolve_imports(ast)
        except Parser.ParserError as e:
            print(f"[!] Parser error in {self.args.source}:")
            e.display()
            sys.exit(1)

        if self.args.output_format == "lexer":
            print(tokens)
            sys.exit(0)
        elif self.args.output_format == "ast":
            print(ast)
            sys.exit(0)
        elif self.args.output_format == "asm":
            typechecker = TypeChecker()
            try:
                typechecker.check(ast)
            except TypeError as e:
                print(f"[!] Type error in {self.args.source}: {e}")
                sys.exit(1)
            codegen = CodeGen()
            print(codegen.generate(ast))
            sys.exit(0)

    def compile_to_object(self, source: str, obj_path: str) -> List[str]:
        parser = Parser(source)
        importer = Importer("lib/")
        try:
            ast = parser.parse()
            ast, imported_modules = importer.resolve_imports(ast)
            if self.args.verbose:
                print(f"[*] Parsed {self.args.source} successfully")
                print(ast)
        except Parser.ParserError as e:
            print(f"[!] Parser error in {self.args.source}:")
            e.display()
            sys.exit(1)

        typechecker = TypeChecker()
        try:
            typechecker.check(ast)
            if self.args.verbose:
                print(f"[*] Type checking completed for {self.args.source}")
        except TypeError as e:
            print(f"[!] Type error in {self.args.source}: {e}")
            sys.exit(1)

        codegen = CodeGen()
        asm_output = codegen.generate(ast)

        asm_path = obj_path[:-2] + ".asm"
        with open(asm_path, "w", encoding="utf-8") as f:
            f.write(asm_output)

        nasm_cmd = ["nasm", "-felf64", asm_path, "-o", obj_path] + self.args.asflags.split()
        if self.args.verbose:
            print(f"[*] Running: {' '.join(nasm_cmd)}")
        try:
            subprocess.run(nasm_cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"[!] Assembly failed for {self.args.source}: {e}")
            sys.exit(1)

        return imported_modules

    def compile_imported_modules(self, imported_modules: List[str]) -> List[str]:
        obj_paths = []
        for mod_path in imported_modules:
            mod_name = os.path.splitext(os.path.basename(mod_path))[0]
            mod_obj_path = os.path.join(self.build_dir, f"{mod_name}.o")
            if self.args.verbose:
                print(f"[*] Compiling imported module: {mod_path}")
            source = self.read_source(mod_path)
            self.compile_to_object(source, mod_obj_path)
            obj_paths.append(mod_obj_path)
        return obj_paths

    def assemble_runtime(self) -> str:
        runtime_obj_path = os.path.join(self.build_dir, "runtime.o")
        nasm_cmd = ["nasm", "-felf64", self.args.runtime, "-o", runtime_obj_path]
        if self.args.verbose:
            print(f"[*] Assembling runtime: {' '.join(nasm_cmd)}")
        try:
            subprocess.run(nasm_cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"[!] Failed to assemble runtime.asm: {e}")
            sys.exit(1)
        return runtime_obj_path

    def link_objects(self, object_files: List[str]) -> None:
        ld_cmd = ["gcc", "-no-pie"] + object_files + ["-o", self.args.output]
        if self.args.verbose:
            print(f"[*] Running: {' '.join(ld_cmd)}")
        try:
            subprocess.run(ld_cmd, check=True)
            if self.args.verbose:
                print(f"[+] Successfully compiled: {self.args.output}")
        except subprocess.CalledProcessError as e:
            print(f"[!] Linking failed: {e}")
            sys.exit(1)

    def run_executable(self) -> None:
        if self.args.run:
            try:
                subprocess.run([f"./{self.args.output}"], check=True)
                if not self.args.no_clean:
                    os.remove(self.args.output)
            except subprocess.CalledProcessError as e:
                print(f"[!] Execution failed: {e}")
                sys.exit(1)

    def compile(self) -> None:
        self.validate_input_files()
        source = self.read_source(self.args.source)
        if self.args.output_format != "bin":
            self.process_non_binary_output(source)
            return
        self.setup_build_directory()
        runtime_obj = self.assemble_runtime()
        main_obj = os.path.join(self.build_dir, "prog.o")
        imported_modules = self.compile_to_object(source, main_obj)
        imported_objs = self.compile_imported_modules(imported_modules)
        all_objs = [runtime_obj, main_obj] + imported_objs
        self.link_objects(all_objs)
        self.run_executable()

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile .sw source files")
    parser.add_argument("source", help="Source file (.sw)")
    parser.add_argument("-o", "--output", default="out", help="Output executable name")
    parser.add_argument("-of", "--output-format", choices=["bin", "asm", "ast", "lexer"], 
                       default="bin", help="Output format: bin (default), asm (stdout), ast (stdout), lexer (stdout)")
    parser.add_argument("--asflags", default="", help="Additional NASM flags")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-r", "--run", action="store_true", 
                       help="Run the output binary after compilation, then remove it")
    parser.add_argument("-nc", "--no-clean", action="store_true", 
                       help="Do not remove the build directory after compilation")
    parser.add_argument("--runtime", default="runtime.asm", help="Path to runtime.asm file")
    return parser.parse_args()

def main():
    args = parse_arguments()
    compiler = Compiler(args)
    try:
        compiler.compile()
    except (FileNotFoundError, IOError) as e:
        print(f"[!] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
