from dataclasses import dataclass
from typing import List, Tuple, Dict, Any
from code_extractor.parsers.parser import ParsedCode
from code_extractor.parsers.wrappers_core import TreeSitterLanguageWrapper

@dataclass
class AstNodeRec:
    id: int
    type: str
    kind: str
    span: Tuple[Tuple[int,int], Tuple[int,int]]
    text: str
    named: bool

class AstExtractor:
    def __init__(self, keep_unnamed: bool = False, text_limit: int = 200):
        self.keep_unnamed = keep_unnamed
        self.text_limit = text_limit

    def _tag_kind(self, node_type: str, kinds_map: Dict[str, set]) -> str:
        if   node_type in kinds_map["function_def"]: return "function_def"
        elif node_type in kinds_map["assignment"]:   return "assignment"
        elif node_type in kinds_map["identifier"]:   return "identifier"
        elif node_type in kinds_map["if_stmt"]:      return "if_stmt"
        elif node_type in kinds_map["loop_stmt"]:    return "loop_stmt"
        elif node_type in kinds_map["call_expr"]:    return "call_expr"
        elif node_type in kinds_map["return_stmt"]:  return "return_stmt"
        else:                                        return "other"

    def extract(self, parsed: "ParsedCode", wrapper: "TreeSitterLanguageWrapper"):
        """
        输入：ParsedCode（含 ast_root / 源）、语言 wrapper（含 kinds 映射）
        输出：nodes（List[AstNodeRec]）、edges_ast（List[(parent_id, child_id)]）
        """
        root = parsed.ast_root
        kinds_map = wrapper.kinds

        nodes: List[AstNodeRec] = []
        edges_ast: List[Tuple[int,int]] = []
        node_to_id: Dict[Any, int] = {}
        next_id = 0

        def alloc_id(node) -> int:
            nonlocal next_id
            if node not in node_to_id:
                node_to_id[node] = next_id
                next_id += 1
            return node_to_id[node]

        # 迭代式 DFS，避免极深递归
        stack = [(root, None)]  # (node, parent_id)
        while stack:
            node, pid = stack.pop()

            # 过滤 unnamed（标点、括号等）可减少噪声
            if not self.keep_unnamed and hasattr(node, "is_named") and not node.is_named:
                # 即便跳过当前节点，也要把它的孩子压栈，让“语义节点”不丢
                for ch in reversed(getattr(node, "children", []) or []):
                    stack.append((ch, pid))
                continue

            nid = alloc_id(node)
            kind = self._tag_kind(node.type, kinds_map)
            text = parsed.text_of(node)
            if len(text) > self.text_limit:
                text = text[: self.text_limit] + "..."

            nodes.append(AstNodeRec(
                id=nid,
                type=node.type,
                kind=kind,
                span=parsed.span(node),
                text=text,
                named=getattr(node, "is_named", True),
            ))

            if pid is not None:
                edges_ast.append((pid, nid))

            # 逆序压栈保证遍历顺序接近源码
            for ch in reversed(getattr(node, "children", []) or []):
                stack.append((ch, nid))

        return nodes, edges_ast
