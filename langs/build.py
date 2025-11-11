#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

import ctypes
from ctypes import c_void_p, c_char_p
from ctypes import PYFUNCTYPE, py_object, pythonapi

import tree_sitter  # Latest version
from tree_sitter import Language, Parser

# Directory where compiled shared libraries (.so/.dylib) will be stored
# You can change it to Path("build") or any other location
BUILD_DIR = Path("build")
BUILD_DIR.mkdir(exist_ok=True)

# Mapping: language name -> grammar source directory
# Note: typescript / tsx grammars are subdirectories
GRAMMARS = {
    "python":      "tree-sitter-python",
    "javascript":  "tree-sitter-javascript",
    # "typescript":  "tree-sitter-typescript/typescript",
    # "tsx":         "tree-sitter-typescript/tsx",
    "c":           "tree-sitter-c",
    "java":        "tree-sitter-java",
}


def build_tree_sitter_language(lang_name: str, src_dir: str):
    """
    Build and compile a tree-sitter grammar in the given src_dir using the
    tree-sitter CLI. The resulting shared library (.so / .dylib / .dll)
    will be copied to BUILD_DIR/<lang_name>.so.
    """
    src_path = Path(src_dir)
    if not src_path.exists():
        raise FileNotFoundError(f"Grammar directory not found: {src_dir}")

    out_lib = BUILD_DIR / f"{lang_name}.so"
    if out_lib.exists():
        print(f"[skip] {lang_name}: {out_lib} already exists")
        return out_lib

    print(f"[build] {lang_name} from {src_dir}")

    # 1) Generate parser source files (parser.c / scanner.c)
    abi = getattr(tree_sitter, "LANGUAGE_VERSION", None)
    if abi is None:
        cmd_gen = ["tree-sitter", "generate"]
    else:
        cmd_gen = ["tree-sitter", "generate", "--abi", str(abi)]
    subprocess.run(cmd_gen, cwd=src_dir, check=True)

    # 2) Compile grammar into a shared library (.so / .dylib / .dll)
    subprocess.run(["tree-sitter", "build"], cwd=src_dir, check=True)

    # 3) Locate the compiled shared library within the grammar directory
    candidates = []
    for p in Path(src_dir).rglob("*.so"):
        candidates.append(p)
    for p in Path(src_dir).rglob("*.dylib"):
        candidates.append(p)
    for p in Path(src_dir).rglob("*.dll"):
        candidates.append(p)

    if not candidates:
        raise RuntimeError(f"No shared library (.so/.dylib/.dll) found after build in {src_dir}")

    lib_path = candidates[0]
    print(f"[found] {lang_name} built at {lib_path}")
    out_lib.write_bytes(lib_path.read_bytes())
    print(f"[copy] {lib_path} -> {out_lib}")
    return out_lib


def load_language_compat(lib_path, lang_name: str) -> Language:
    """
    Load a tree-sitter language library with backward compatibility:
    - For older API versions: Language(path, name)
    - For newer API versions: Language(capsule)
      (construct a PyCapsule via ctypes if only the capsule interface is supported)
    """
    lib_path = str(lib_path)

    # Try the old API first: Language(path, name)
    try:
        return Language(lib_path, lang_name)
    except TypeError:
        # New API: only accepts a capsule pointer, so build it manually using ctypes
        cdll = ctypes.CDLL(os.path.abspath(lib_path))

        # Most grammars export a function named tree_sitter_<lang_name>
        func_name = f"tree_sitter_{lang_name}"
        if not hasattr(cdll, func_name):
            # Some grammars export tree_sitter_<lang_name>_language instead
            alt = func_name + "_language"
            if hasattr(cdll, alt):
                func_name = alt
            else:
                raise RuntimeError(
                    f"Cannot find symbol {func_name} or {alt} in {lib_path}"
                )

        func = getattr(cdll, func_name)
        func.restype = c_void_p
        ptr = func()

        # Wrap the raw pointer into a PyCapsule to pass to Language()
        PyCapsule_New = PYFUNCTYPE(py_object, c_void_p, c_char_p, c_void_p)(
            ("PyCapsule_New", pythonapi)
        )
        capsule = PyCapsule_New(ptr, b"tree_sitter.Language", None)
        return Language(capsule)


def test_languages(built_libs):
    """
    Basic functionality test:
    Attempt to load each built language and parse a short example snippet.
    This ensures the grammar is correctly compiled and can produce a syntax tree.
    """
    samples = {
        "python": "def add(a, b):\n    return a + b\n",
        "javascript": "function add(a, b) { return a + b; }",
        "c": "int add(int a, int b) { return a + b; }",
        "java": "class Test { int add(int a, int b) { return a + b; } }",
    }

    print("\n=== Simple Language Test ===")
    for lang_name, lib_path in built_libs.items():
        print(f"\n[Testing] {lang_name}")
        try:
            lang = load_language_compat(lib_path, lang_name)
            parser = Parser(lang)

            code = samples.get(lang_name, "a=b+c;").encode("utf-8")
            tree = parser.parse(code)
            root = tree.root_node
            print(f"  ✓ Loaded and parsed successfully.")
            print(f"  Root node: {root.type}")
            print(f"  Child count: {len(root.children)}")
            if root.children:
                print(f"  First child: {root.children[0].type}")
        except Exception as e:
            print(f"  ✗ Failed to load or parse: {e}")


def main():
    """
    Build all grammars defined in GRAMMARS and test the generated libraries.
    """
    BUILD_DIR.mkdir(exist_ok=True)
    built_libs = {}
    for lang_name, src in GRAMMARS.items():
        lib = build_tree_sitter_language(lang_name, src)
        built_libs[lang_name] = lib

    print("\nBuild finished. Generated libraries:")
    for name, path in built_libs.items():
        print(f"  {name}: {path}")

    # Run the test suite after building
    # test_languages(built_libs)


if __name__ == "__main__":
    main()
