from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional

from code_extractor.parsers.ast import AstNodeRec
from code_extractor.graphs.ast_index import AstIndex


# =========================
#   Data structures
# =========================

@dataclass
class DefUseGraph:
    """
    Def-Use information on top of normalized AST.

    defs:
        node_id -> set of human-readable symbol strings defined at this node
    uses:
        node_id -> set of human-readable symbol strings used at this node
    edges:
        list of (def_node_id, use_node_id, symbol_string)
    """
    defs: Dict[int, Set[str]] = field(default_factory=dict)
    uses: Dict[int, Set[str]] = field(default_factory=dict)
    edges: List[Tuple[int, int, str]] = field(default_factory=list)


@dataclass(frozen=True)
class SymbolKey:
    """
    Canonical key for a symbol in the def-use analysis.

    kind:
        "var"   – local / global variable, parameter
        "field" – object / struct field (attr access)
        "type"  – type name (Point, T, etc.)
        "func"  – function / method name
        "class" – class / struct / enum name
    name:
        base name of the symbol (e.g., "x", "Point")
    qualifier:
        for fields: receiver name (e.g., "self", "this", "p")
        for others: usually None
    """
    kind: str
    name: str
    qualifier: Optional[str] = None


# =========================
#   Small helpers
# =========================

# 哪些 AstNodeRec.kind 被视为“标识符式的使用”
IDENT_LIKE_KINDS: Set[str] = {"identifier", "attr_access"}


def is_ident_like(node: AstNodeRec) -> bool:
    return node.kind in IDENT_LIKE_KINDS


def symbol_to_str(sym: SymbolKey) -> str:
    """
    Human-readable string for a symbol.

    - var / type / func / class: just use sym.name
    - field: show "qual.name" if qualifier is meaningful; otherwise just name

    Special case:
      if qualifier == name (e.g. res.res) we just print "res" to avoid ugly
      strings, but SymbolKey 仍然保留完整信息用于内部区分。
    """
    if sym.kind == "field":
        if sym.qualifier and sym.qualifier != sym.name:
            return f"{sym.qualifier}.{sym.name}"
        return sym.name
    # 其他种类直接用 name
    return sym.name


def ensure_defs(graph: DefUseGraph, nid: int) -> Set[str]:
    if nid not in graph.defs:
        graph.defs[nid] = set()
    return graph.defs[nid]


def ensure_uses(graph: DefUseGraph, nid: int) -> Set[str]:
    if nid not in graph.uses:
        graph.uses[nid] = set()
    return graph.uses[nid]


def lookup_def(scope_stack: List[Dict[SymbolKey, int]], sym: SymbolKey) -> Optional[int]:
    """
    Look up the closest definition of `sym` from innermost to outermost scope.
    Scope maps use SymbolKey, so fields / vars / types live in separate namespaces.
    """
    for scope in reversed(scope_stack):
        if sym in scope:
            return scope[sym]
    return None


def build_symbol_key(nid: int, index: AstIndex) -> Optional[SymbolKey]:
    """
    Build a SymbolKey from a given AST node id.

    We only interpret:
      - identifier           -> var / type
      - attr_access          -> field (using textual split on '.' or '->')
    """
    node = index.nodes_by_id[nid]
    text = node.text.strip()

    if not text:
        return None

    # Plain identifier: either type or var
    if node.kind == "identifier":
        if node.type == "type_identifier":
            return SymbolKey(kind="type", name=text)
        return SymbolKey(kind="var", name=text)

    # Attribute / field access: e.g. self.x, this.x, p.x, p->x, q.y
    if node.kind == "attr_access":
        raw = text

        # Choose a delimiter: try '->' then '.', others可以以后再扩展
        base = None
        field = raw
        if "->" in raw:
            base, field = raw.split("->", 1)
        elif "." in raw:
            base, field = raw.split(".", 1)

        base = (base or "").strip() or None
        field = field.strip()
        if not field:
            return None

        return SymbolKey(kind="field", name=field, qualifier=base)

    return None


def find_function_name_id(
    fn_id: int,
    index: AstIndex,
) -> Optional[int]:
    """
    Find the identifier node that should be considered the function / method name.

    - Python / JS / Java:
        function_def node has direct child with kind="identifier"
    - C:
        function_definition -> function_declarator -> identifier

    Avoid parameters by skipping identifiers whose ancestors contain
    param_list / param_decl.
    """
    nodes = index.nodes_by_id
    children = index.children
    parent = index.parent

    # 1) direct child
    for cid in children.get(fn_id, []):
        if nodes[cid].kind == "identifier":
            return cid

    # 2) BFS downwards looking for identifier not under param_list/param_decl
    from collections import deque
    q = deque(children.get(fn_id, []))
    while q:
        nid = q.popleft()
        node = nodes[nid]
        if node.kind == "identifier":
            anc = parent.get(nid)
            skip = False
            while anc is not None and anc != fn_id:
                akind = nodes[anc].kind
                if akind in ("param_list", "param_decl"):
                    skip = True
                    break
                anc = parent.get(anc)
            if not skip:
                return nid
        q.extend(children.get(nid, []))
    return None


def find_class_name_id(
    class_id: int,
    index: AstIndex,
) -> Optional[int]:
    """
    Find the identifier node for class / struct / enum name.

    - Java / JS:
        class_declaration -> identifier
    - C:
        struct_specifier / enum_specifier / union_specifier -> type_identifier
        (already normalized to kind="identifier")
    """
    nodes = index.nodes_by_id
    children = index.children
    for cid in children.get(class_id, []):
        if nodes[cid].kind == "identifier":
            return cid
    return None


# =========================
#   Main builder
# =========================

def build_def_use(index: AstIndex) -> DefUseGraph:
    """
    Build a coarse def-use graph on top of normalized AST (AstNodeRec + AstIndex).

    Heuristics:
      - function_def:
          * function name is a def in the outer scope (kind="func")
          * opens a new local scope for params / locals.
      - class_def:
          * class / struct / enum name is a def in the current scope (kind="class").
      - param_list:
          * identifiers inside are parameter defs in the current function scope
            (kind="var").
      - param_decl:
          * identifiers inside are parameter / local variable defs (kind="var").
      - assignment:
          * first ident-like child (identifier or attr_access) is LHS def;
            remaining ident-like children are uses.
      - ident-like node (identifier / attr_access):
          * if not already classified as def, treated as use; linked to nearest
            preceding definition in scope_stack by SymbolKey.
    """
    nodes = index.nodes_by_id
    children = index.children
    parent = index.parent

    g = DefUseGraph()

    # 链表式作用域栈，里层优先
    scope_stack: List[Dict[SymbolKey, int]] = [dict()]  # global / outermost scope

    # 记录哪些节点已经被当作 def 处理过
    nodes_marked_as_def: Set[int] = set()

    def dfs(nid: int):
        node = nodes[nid]

        # ---------- pre-order actions ----------

        # 1) function_def
        if node.kind == "function_def":
            fn_name_id = find_function_name_id(nid, index)
            if fn_name_id is not None:
                fn_node = nodes[fn_name_id]
                fn_name = fn_node.text.strip()
                if fn_name:
                    sym = SymbolKey(kind="func", name=fn_name)
                    s = symbol_to_str(sym)
                    defs_set = ensure_defs(g, fn_name_id)
                    defs_set.add(s)
                    scope_stack[-1][sym] = fn_name_id
                    nodes_marked_as_def.add(fn_name_id)

            # push function-local scope
            scope_stack.append({})

        # 2) class_def
        if node.kind == "class_def":
            cls_id = find_class_name_id(nid, index)
            if cls_id is not None:
                cls_node = nodes[cls_id]
                cls_name = cls_node.text.strip()
                if cls_name:
                    sym = SymbolKey(kind="class", name=cls_name)
                    s = symbol_to_str(sym)
                    defs_set = ensure_defs(g, cls_id)
                    defs_set.add(s)
                    scope_stack[-1][sym] = cls_id
                    nodes_marked_as_def.add(cls_id)

        # 3) param_list: 参数定义
        if node.kind == "param_list":
            for cid in children.get(nid, []):
                sym = build_symbol_key(cid, index)
                if sym is None:
                    continue
                # 我们只把 var 当作参数；type / field 不在这里处理
                if sym.kind != "var":
                    continue
                s = symbol_to_str(sym)
                if not s:
                    continue
                defs_set = ensure_defs(g, cid)
                defs_set.add(s)
                scope_stack[-1][sym] = cid
                nodes_marked_as_def.add(cid)

        # 4) param_decl: 参数 / 局部变量定义（C/Java/JS 等）
        if node.kind == "param_decl":
            for cid in children.get(nid, []):
                sym = build_symbol_key(cid, index)
                if sym is None:
                    continue
                if sym.kind != "var":
                    continue
                s = symbol_to_str(sym)
                if not s:
                    continue
                defs_set = ensure_defs(g, cid)
                defs_set.add(s)
                scope_stack[-1][sym] = cid
                nodes_marked_as_def.add(cid)

        # 5) assignment: 第一个 ident-like 是 LHS def，其余是 use
        if node.kind == "assignment":
            ident_children: List[int] = [
                cid for cid in children.get(nid, [])
                if is_ident_like(nodes[cid])
            ]
            ident_children.sort(key=lambda cid: nodes[cid].span[0])

            if ident_children:
                # LHS
                lhs_id = ident_children[0]
                lhs_sym = build_symbol_key(lhs_id, index)
                if lhs_sym is not None and lhs_sym.name:
                    s = symbol_to_str(lhs_sym)
                    defs_set = ensure_defs(g, lhs_id)
                    defs_set.add(s)
                    scope_stack[-1][lhs_sym] = lhs_id
                    nodes_marked_as_def.add(lhs_id)

                # RHS identifiers as uses
                for uid in ident_children[1:]:
                    use_sym = build_symbol_key(uid, index)
                    if use_sym is None or not use_sym.name:
                        continue
                    su = symbol_to_str(use_sym)
                    uses_set = ensure_uses(g, uid)
                    uses_set.add(su)
                    def_id = lookup_def(scope_stack, use_sym)
                    if def_id is not None:
                        g.edges.append((def_id, uid, su))

        # 6) standalone ident-like nodes as uses
        if is_ident_like(node) and nid not in nodes_marked_as_def:
            sym = build_symbol_key(nid, index)
            if sym is not None and sym.name:
                su = symbol_to_str(sym)
                uses_set = ensure_uses(g, nid)
                uses_set.add(su)
                def_id = lookup_def(scope_stack, sym)
                if def_id is not None:
                    g.edges.append((def_id, nid, su))

        # ---------- recurse into children ----------
        for cid in children.get(nid, []):
            dfs(cid)

        # ---------- post-order actions ----------
        if node.kind == "function_def":
            scope_stack.pop()

    # 找所有根节点（通常只有一个）
    root_ids = getattr(index, "root_ids", None)
    if not root_ids:
        root_ids = [nid for nid, p in parent.items() if p is None]

    for rid in root_ids:
        dfs(rid)

    return g