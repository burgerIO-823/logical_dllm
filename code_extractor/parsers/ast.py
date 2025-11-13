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
        # 结构类优先
        if node_type in kinds_map.get("root", set()):       return "root"
        if node_type in kinds_map.get("class_def", set()):  return "class_def"
        if node_type in kinds_map.get("block", set()):      return "block"
        if node_type in kinds_map.get("param_list", set()): return "param_list"
        if node_type in kinds_map.get("param_decl", set()): return "param_decl"
        if node_type in kinds_map.get("attr_access", set()): return "attr_access"

        # 可选表达式/类型类
        if node_type in kinds_map.get("compare_expr", set()): return "compare_expr"
        if node_type in kinds_map.get("paren_expr", set()):   return "paren_expr"
        if node_type in kinds_map.get("literal_int", set()):  return "literal_int"
        if node_type in kinds_map.get("type_spec", set()):    return "type_spec"

        # 原来的 7 类
        if   node_type in kinds_map.get("function_def", set()): return "function_def"
        elif node_type in kinds_map.get("assignment", set()):   return "assignment"
        elif node_type in kinds_map.get("identifier", set()):   return "identifier"
        elif node_type in kinds_map.get("if_stmt", set()):      return "if_stmt"
        elif node_type in kinds_map.get("loop_stmt", set()):    return "loop_stmt"
        elif node_type in kinds_map.get("call_expr", set()):    return "call_expr"
        elif node_type in kinds_map.get("return_stmt", set()):  return "return_stmt"
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
