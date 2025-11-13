from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional

from code_extractor.parsers.ast import AstNodeRec
from code_extractor.graphs.ast_index import AstIndex


@dataclass
class DefUseGraph:
    """
    Def-Use information on top of normalized AST.

    defs:
        node_id -> set of variable names defined at this node
    uses:
        node_id -> set of variable names used at this node
    edges:
        list of (def_node_id, use_node_id, var_name)
    """
    defs: Dict[int, Set[str]] = field(default_factory=dict)
    uses: Dict[int, Set[str]] = field(default_factory=dict)
    edges: List[Tuple[int, int, str]] = field(default_factory=list)


def build_def_use(index: AstIndex) -> DefUseGraph:
    """
    Build a coarse def-use graph using AstNodeRec kinds and simple scoping rules.

    Heuristics (first version):
      - function_def: opens a new local scope.
      - param_list: identifiers inside are parameter definitions in current scope.
      - param_decl: identifiers inside are parameter/var definitions in current scope.
      - assignment: first identifier child (by span start) is LHS definition; others are uses.
      - identifier: if not already marked as a def, treated as use; linked to nearest
                    preceding definition in the scope stack.

    Notes:
      - This is intentionally conservative and simple; we can refine language-specific
        patterns later.
    """
    nodes = index.nodes_by_id
    children = index.children
    parent = index.parent

    g = DefUseGraph()
    # Helper: ensure dict entries exist
    def ensure_defs(nid: int) -> Set[str]:
        if nid not in g.defs:
            g.defs[nid] = set()
        return g.defs[nid]

    def ensure_uses(nid: int) -> Set[str]:
        if nid not in g.uses:
            g.uses[nid] = set()
        return g.uses[nid]

    # Scope stack: list of {var_name -> def_node_id}
    scope_stack: List[Dict[str, int]] = [dict()]  # global scope

    def lookup_def(var_name: str) -> Optional[int]:
        for scope in reversed(scope_stack):
            if var_name in scope:
                return scope[var_name]
        return None

    # Keep track of which identifier nodes are already classified as defs
    identifiers_marked_as_def: Set[int] = set()

    # 需要前序+后序，所以写一个递归 DFS
    def dfs(nid: int):
        node = nodes[nid]

        # --- pre-order actions ---
        # Enter function scope
        if node.kind == "function_def":
            # 新开一个函数局部作用域
            scope_stack.append({})

        # Parameter list: treat child identifiers as defs
        if node.kind == "param_list":
            for cid in children.get(nid, []):
                child = nodes[cid]
                if child.kind == "identifier":
                    name = child.text.strip()
                    if not name:
                        continue
                    ensure_defs(cid).add(name)
                    scope_stack[-1][name] = cid
                    identifiers_marked_as_def.add(cid)

        # Parameter declaration (C/Java etc.)
        if node.kind == "param_decl":
            for cid in children.get(nid, []):
                child = nodes[cid]
                if child.kind == "identifier":
                    name = child.text.strip()
                    if not name:
                        continue
                    ensure_defs(cid).add(name)
                    scope_stack[-1][name] = cid
                    identifiers_marked_as_def.add(cid)

        # Assignment: first identifier child is LHS def; others are uses
        if node.kind == "assignment":
            ident_children: List[int] = [
                cid for cid in children.get(nid, [])
                if nodes[cid].kind == "identifier"
            ]

            # 排序：按起始 span (row, col)
            ident_children.sort(
                key=lambda cid: nodes[cid].span[0]
            )  # span is ((row,col),(row,col))

            if ident_children:
                lhs_id = ident_children[0]
                lhs_node = nodes[lhs_id]
                lhs_name = lhs_node.text.strip()
                if lhs_name:
                    ensure_defs(lhs_id).add(lhs_name)
                    scope_stack[-1][lhs_name] = lhs_id
                    identifiers_marked_as_def.add(lhs_id)

                # 剩下的 identifier 作为 use
                for uid in ident_children[1:]:
                    use_node = nodes[uid]
                    uname = use_node.text.strip()
                    if not uname:
                        continue
                    ensure_uses(uid).add(uname)
                    def_id = lookup_def(uname)
                    if def_id is not None:
                        g.edges.append((def_id, uid, uname))

        # Standalone identifier: treat as use if not marked as def
        if node.kind == "identifier" and nid not in identifiers_marked_as_def:
            name = node.text.strip()
            if name:
                ensure_uses(nid).add(name)
                def_id = lookup_def(name)
                if def_id is not None:
                    g.edges.append((def_id, nid, name))

        # --- recurse into children ---
        for cid in children.get(nid, []):
            dfs(cid)

        # --- post-order actions ---
        # Exit function scope
        if node.kind == "function_def":
            scope_stack.pop()

    # 找到所有根（parent 为 None 的节点），通常只有一个
    root_ids = [nid for nid, p in parent.items() if p is None]
    for rid in root_ids:
        dfs(rid)

    return g