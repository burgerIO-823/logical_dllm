from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from code_extractor.parsers.ast import AstNodeRec


@dataclass
class AstIndex:
    """
    Normalized index over extracted AST nodes.

    - nodes_by_id:   node_id -> AstNodeRec
    - children:      parent_id -> list of child_ids (in AST/approx source order)
    - parent:        node_id -> parent_id (or None for roots)
    - preorder:      node_ids in the order returned by AstExtractor
    """
    nodes_by_id: Dict[int, AstNodeRec]
    children: Dict[int, List[int]]
    parent: Dict[int, Optional[int]]
    preorder: List[int]


def build_ast_index(
    nodes: List[AstNodeRec],
    edges_ast: List[Tuple[int, int]],
) -> AstIndex:
    """
    Build a normalized AST index from node list and AST edges.

    We assume edges_ast contains (parent_id, child_id) pairs produced
    by AstExtractor.extract.
    """
    nodes_by_id: Dict[int, AstNodeRec] = {n.id: n for n in nodes}

    # Initialize children and parent maps
    children: Dict[int, List[int]] = {n.id: [] for n in nodes}
    parent: Dict[int, Optional[int]] = {n.id: None for n in nodes}

    for p, c in edges_ast:
        # Be robust to any stray ids
        if p not in children:
            children[p] = []
        children[p].append(c)
        parent[c] = p

    # Preorder: AstExtractor already did a DFS-like traversal; we keep that order
    preorder: List[int] = [n.id for n in nodes]

    return AstIndex(
        nodes_by_id=nodes_by_id,
        children=children,
        parent=parent,
        preorder=preorder,
    )