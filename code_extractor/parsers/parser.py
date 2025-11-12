from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from tree_sitter import Parser
from code_extractor.parsers.wrappers_core import TreeSitterLanguageWrapper


# ---------- Unified payload ----------
@dataclass
class ParsedCode:
    language: str
    ast_root: Any           # tree-sitter Node
    source: str             # original source (str)
    source_bytes: bytes     # utf-8 encoded bytes for byte-slice safe extraction

    def text_of(self, node) -> str:
        # Safe slice from byte offsets; tree-sitter uses byte indices.
        return self.source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")

    def span(self, node):
        # ((row,col), (row,col)) zero-based
        return node.start_point, node.end_point


# ---------- Abstract interface ----------
class CodeParser:
    def parse(self, code: str, language: str) -> ParsedCode:
        raise NotImplementedError


# ---------- Concrete tree-sitter front-end ----------
class TreeSitterCodeParser(CodeParser):
    """
    Thin front-end that delegates to a pre-built TreeSitterLanguageWrapper
    per language. Each wrapper owns (Language, Parser(language), config).
    """
    def __init__(self, language_wrappers: Dict[str, TreeSitterLanguageWrapper]):
        # e.g. {"python": py_wrapper, "javascript": js_wrapper, ...}
        self.languages = language_wrappers

    def parse(self, code: str, language: str) -> ParsedCode:
        if language not in self.languages:
            raise KeyError(
                f"[TreeSitterCodeParser] Language '{language}' is not registered. "
                f"Available: {list(self.languages.keys())}"
            )
        wrapper = self.languages[language]
        if not isinstance(wrapper, TreeSitterLanguageWrapper):
            raise TypeError(
                f"[TreeSitterCodeParser] Wrapper for '{language}' must be a "
                f"TreeSitterLanguageWrapper, got {type(wrapper)}"
            )

        data = code.encode("utf-8")
        tree = wrapper.parser.parse(data)
        return ParsedCode(
            language=language,
            ast_root=tree.root_node,
            source=code,
            source_bytes=data,
        )


# ---------- Convenience helpers (optional) ----------
def build_parser_from_registry(registry, languages: Optional[list[str]] = None) -> TreeSitterCodeParser:
    """
    Convenience: construct a TreeSitterCodeParser directly from your LanguageRegistry.
    If `languages` is None, we will use all languages registered in the registry.
    """
    if languages is None:
        languages = registry.list_languages()
    wrappers: Dict[str, TreeSitterLanguageWrapper] = {
        lang: registry.get_wrapper(lang) for lang in languages
    }
    return TreeSitterCodeParser(wrappers)


def quick_parse(registry, code: str, language: str) -> ParsedCode:
    """
    One-liner helper for quick experiments:
      parsed = quick_parse(reg, "def f(): pass", "python")
    """
    parser = build_parser_from_registry(registry, [language])
    return parser.parse(code, language)
