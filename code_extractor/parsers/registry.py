from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Callable, Any
from pathlib import Path
from tree_sitter import Language
from code_extractor.parsers.wrappers_core import TreeSitterLanguageWrapper

RequiredCfgKeys = [
    "function_def_types","assignment_types","identifier_types",
    "if_types","loop_types","call_types","return_types",
]

def validate_config(lang: str, cfg: dict):
    missing = [k for k in RequiredCfgKeys if k not in cfg]
    if missing:
        raise ValueError(f"[{lang}] config missing keys: {missing}")
    for k in RequiredCfgKeys:
        v = cfg[k]
        if not isinstance(v, (list, tuple, set)) or not v:
            raise ValueError(f"[{lang}] config[{k}] should be non-empty list/tuple/set")

@dataclass
class LangMeta:
    name: str
    lib_path: Path
    config: dict
    grammar_version: Optional[str] = None      # e.g. "tree-sitter-python 0.21"
    api_version: Optional[str] = None          # e.g. "LANGUAGE_VERSION=15"
    notes: Optional[str] = None                # any comments

class LanguageRegistry:
    def __init__(self):
        self._meta: Dict[str, LangMeta] = {}
        self._wrappers: Dict[str, TreeSitterLanguageWrapper] = {}
        self._constructors: Dict[str, Callable[[LangMeta], TreeSitterLanguageWrapper]] = {}

    # ---- 手动注册元信息（轻量，不加载库） ----
    def register_meta(self, meta: LangMeta):
        if meta.name in self._meta:
            raise KeyError(f"Language {meta.name} already registered")
        validate_config(meta.name, meta.config)
        if not meta.lib_path.exists():
            raise FileNotFoundError(f"[{meta.name}] shared lib not found: {meta.lib_path}")
        self._meta[meta.name] = meta

    # ---- 手动注册构造函数（可替换默认 wrapper）----
    def register_constructor(self, lang_name: str,
                             ctor: Callable[[LangMeta], TreeSitterLanguageWrapper]):
        self._constructors[lang_name] = ctor

    # ---- 获取 wrapper（延迟加载、带缓存） ----
    def get_wrapper(self, lang_name: str) -> TreeSitterLanguageWrapper:
        if lang_name in self._wrappers:
            return self._wrappers[lang_name]
        meta = self._meta.get(lang_name)
        if not meta:
            raise KeyError(f"Language {lang_name} not registered. Call register_meta(...) first.")

        ctor = self._constructors.get(lang_name, self._default_constructor)
        wrapper = ctor(meta)
        self._wrappers[lang_name] = wrapper
        return wrapper

    # ---- 列表/卸载/重载 ----
    def list_languages(self):
        return list(self._meta.keys())

    def reload(self, lang_name: str):
        if lang_name in self._wrappers:
            del self._wrappers[lang_name]
        return self.get_wrapper(lang_name)

    # ---- 默认构造：从 .so 加载 Language + 注入 config ----
    @staticmethod
    def _default_constructor(meta: LangMeta) -> TreeSitterLanguageWrapper:
        # 兼容新老 API 的加载（你已经实现过），这里假设直接用 Language(lib_path, name)
        try:
            lang = Language(str(meta.lib_path), meta.name)
        except TypeError:
            # 如遇到新版只接收 capsule，可调用你现有的 load_language_compat
            from .loaders import load_language_compat
            lang = load_language_compat(meta.lib_path, meta.name)
        from .wrappers_core import TreeSitterLanguageWrapper
        return TreeSitterLanguageWrapper(language=lang, config=meta.config)
