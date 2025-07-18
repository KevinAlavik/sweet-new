import sys
import subprocess
import tempfile
import os
import argparse
from core.parser import Parser
from core.typechecker import TypeChecker, TypeError
from core.codegen import CodeGen
from core.importer import Importer

def compile_source_to_obj(source_path, obj_path, asflags, verbose):
    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            source = f.read()
    except IOError as e:
        print(f"[!] Failed to read file {source_path}: {e}")
        sys.exit(1)

    parser = Parser(source)
    importer = Importer("lib/")
    try:
        ast = parser.parse()
        ast = importer.resolve_imports(ast)
        print(ast)
    except Parser.ParserError as e:
        print(f"[!] Parser error in {source_path}:")
        e.display()
        sys.exit(1)

    if verbose:
        print(f"[*] Parsed {source_path} successfully")

    typechecker = TypeChecker()
    try:
        typechecker.check(ast)
    except TypeError as e:
        print(f"[!] Type error in {source_path}: {e}")
        sys.exit(1)

    if verbose:
        print(f"[*] Type checking completed for {source_path}")

    codegen = CodeGen()
    asm_output = codegen.generate(ast)

    asm_path = obj_path[:-2] + ".asm"
    with open(asm_path, "w", encoding="utf-8") as f:
        f.write(asm_output)

    nasm_cmd = ["nasm", "-felf64", asm_path, "-o", obj_path] + asflags.split()
    if verbose:
        print(f"[*] Running: {' '.join(nasm_cmd)}")
    try:
        subprocess.run(nasm_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[!] Assembly failed for {source_path}: {e}")
        sys.exit(1)

def assemble_runtime(runtime_asm_path, build_dir, verbose):
    runtime_obj_path = os.path.join(build_dir, "runtime.o")
    if not os.path.exists(runtime_asm_path):
        print(f"[!] Error: runtime.asm not found at {runtime_asm_path}")
        sys.exit(1)

    nasm_cmd = ["nasm", "-felf64", runtime_asm_path, "-o", runtime_obj_path]
    if verbose:
        print(f"[*] Assembling runtime: {' '.join(nasm_cmd)}")
    try:
        subprocess.run(nasm_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[!] Failed to assemble runtime.asm: {e}")
        sys.exit(1)

    return runtime_obj_path

def main():
    parser = argparse.ArgumentParser(description="Compile .sw source files")
    parser.add_argument("source", help="Source file (.sw)")
    parser.add_argument("-o", "--output", default="out", help="Output executable name")
    parser.add_argument("-of", "--output-format", choices=["bin", "asm", "ast", "lexer"], default="bin",
                        help="Output format: bin (default), asm (stdout), ast (stdout), lexer (stdout)")
    parser.add_argument("--asflags", default="", help="Additional NASM flags")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-r", "--run", action="store_true", help="Run the output binary after compilation, then remove it")
    parser.add_argument("-nc", "--no-clean", action="store_true", help="Do not remove the build directory after compilation")
    parser.add_argument("--runtime-asm", default="runtime.asm", help="Path to runtime.asm file")

    args = parser.parse_args()

    main_source = args.source
    runtime_asm_path = args.runtime_asm

    if not os.path.exists(main_source):
        print(f"[!] Error: {main_source} not found.")
        sys.exit(1)
    if not os.path.exists(runtime_asm_path):
        print(f"[!] Error: {runtime_asm_path} not found.")
        sys.exit(1)

    if args.output_format != "bin":
        with open(main_source, 'r', encoding='utf-8') as f:
            source = f.read()
        try:
            full_source = importer.resolve_imports(source, os.path.dirname(main_source))
        except Exception as e:
            print(f"[!] Import resolution error in {main_source}: {e}")
            sys.exit(1)

        parser = Parser(full_source)
        try:
            ast = parser.parse()
            tokens = parser.tokens
        except Parser.ParserError as e:
            print(f"[!] Parser error in {main_source}:")
            e.display()
            sys.exit(1)

        if args.output_format == "lexer":
            print(tokens)
            sys.exit(0)
        elif args.output_format == "ast":
            print(ast)
            sys.exit(0)
        elif args.output_format == "asm":
            typechecker = TypeChecker()
            try:
                typechecker.check(ast)
            except TypeError as e:
                print(f"[!] Type error in {main_source}: {e}")
                sys.exit(1)
            codegen = CodeGen()
            asm_output = codegen.generate(ast)
            print(asm_output)
            sys.exit(0)

    tempdir = None
    if not args.no_clean:
        tempdir = tempfile.TemporaryDirectory()
        build_dir = tempdir.name
    else:
        build_dir = "build"
        os.makedirs(build_dir, exist_ok=True)

    runtime_obj = assemble_runtime(runtime_asm_path, build_dir, args.verbose)

    main_obj = os.path.join(build_dir, "prog.o")

    compile_source_to_obj(main_source, main_obj, args.asflags, args.verbose)

    out_path = args.output
    ld_cmd = ["ld", runtime_obj, main_obj, "-o", out_path]
    if args.verbose:
        print(f"[*] Running: {' '.join(ld_cmd)}")
    try:
        subprocess.run(ld_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[!] Linking failed: {e}")
        sys.exit(1)

    if args.verbose:
        print(f"[+] Successfully compiled: {out_path}")

    if args.run:
        try:
            subprocess.run([f"./{out_path}"], check=True)
            if not args.no_clean:
                os.remove(out_path)
        except subprocess.CalledProcessError as e:
            print(f"[!] Execution failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
