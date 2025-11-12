from dataclasses import dataclass
from typing import Dict, Any, Optional
from tree_sitter import Language, Parser

# —— 统一的数据承载 —— #
@dataclass
class ParsedCode:
    language: str
    ast_root: Any          # tree-sitter Node
    source: str            # str
    source_bytes: bytes    # 用于按 byte slice 提取片段

    def text_of(self, node) -> str:
        return self.source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")

    def span(self, node):
        # ((row,col), (row,col))
        return node.start_point, node.end_point

class CodeParser:
    def parse(self, code: str, language: str) -> ParsedCode:
        raise NotImplementedError