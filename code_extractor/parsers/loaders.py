import os
import ctypes
from ctypes import c_void_p, c_char_p
from ctypes import PYFUNCTYPE, py_object, pythonapi
from tree_sitter import Language

def load_language_compat(lib_path, lang_name: str) -> Language:
    """
    Compatibility loader for tree_sitter.Language.

    - First try old API: Language(<lib_path>, <lang_name>)
    - If that raises TypeError (capsule-only new API), then:
        * dlopen the shared lib,
        * resolve exported symbol: tree_sitter_<lang_name> (or ..._language),
        * get C pointer, wrap with PyCapsule, feed into Language(capsule).
    """
    lib_path = str(lib_path)

    # Old API path
    try:
        return Language(lib_path, lang_name)
    except TypeError:
        pass

    # New API (capsule) path
    cdll = ctypes.CDLL(os.path.abspath(lib_path))

    func_name = f"tree_sitter_{lang_name}"
    if not hasattr(cdll, func_name):
        alt = func_name + "_language"
        if hasattr(cdll, alt):
            func_name = alt
        else:
            raise RuntimeError(
                f"Cannot find symbol '{func_name}' or '{alt}' in {lib_path}"
            )

    func = getattr(cdll, func_name)
    func.restype = c_void_p
    ptr = func()

    PyCapsule_New = PYFUNCTYPE(py_object, c_void_p, c_char_p, c_void_p)(
        ("PyCapsule_New", pythonapi)
    )
    capsule = PyCapsule_New(ptr, b"tree_sitter.Language", None)
    return Language(capsule)