# code_extractor/graphs/logic_graph.py

"""
Logic Graph: Combines CFG and Def-Use information to create a high-level
logical abstraction of code execution and data flow.

This graph represents:
- Statement nodes (module-level code)
- Data dependency edges (based on def-use analysis)
- Function call edges (from statements to function definitions)
- Function definitions with their internal structure
"""

from __future__ import annotations
from typing import Dict, List, Set, Optional
from dataclasses import dataclass

from code_extractor.graphs.cfg import ControlFlowGraph, CallSite, FunctionCFG
from code_extractor.graphs.def_use import DefUseGraph
from code_extractor.graphs.ast_index import AstIndex


@dataclass
class DataDependencyEdge:
    """
    Represents a data dependency between two statements.

    Attributes:
        source_id: ID of the statement that defines variables
        target_id: ID of the statement that uses those variables
        shared_symbols: Set of variable names that create the dependency
    """
    source_id: int
    target_id: int
    shared_symbols: Set[str]


@dataclass
class LogicGraph:
    """
    High-level logical abstraction combining CFG and def-use information.

    Attributes:
        statement_nodes: Set of statement node IDs (module-level)
        data_edges: Data dependency edges between statements
        call_edges: Function call edges (from module/entry to functions)
        function_call_edges: Function-to-function call edges (NEW)
        function_defs: Map of function_id -> function CFG
        entry_point: Entry point ID (-1 for module level, or main function ID)
    """
    statement_nodes: Set[int]
    data_edges: List[DataDependencyEdge]
    call_edges: List[CallSite]
    function_call_edges: List[CallSite]  # NEW: Function → Function calls
    function_defs: Dict[int, FunctionCFG]
    entry_point: int = -1


def _find_main_function(cfg: ControlFlowGraph, index: AstIndex) -> Optional[int]:
    """
    Find the main function/method in the CFG.

    Looks for functions named 'main' or 'Main'.

    Returns:
        The function ID of main, or None if not found
    """
    for func_id, fcfg in cfg.functions.items():
        func_node = index.nodes_by_id.get(func_id)
        if func_node:
            # Get function name from first line
            first_line = func_node.text.split('\n')[0].lower()
            # Check if it contains 'main'
            if 'main' in first_line:
                return func_id
    return None


def _is_descendant_of(node_id: int, ancestor_ids: Set[int], index: AstIndex) -> bool:
    """
    Check if node_id is a descendant of any node in ancestor_ids.
    Used to detect if a call is inside a compound statement (loop/if).
    """
    current = node_id
    while current is not None:
        if current in ancestor_ids:
            return True
        current = index.parent.get(current)
    return False


def _is_in_function(node_id: int, functions: Dict[int, FunctionCFG]) -> Optional[int]:
    """
    Check if node_id is inside a function body.
    Returns the function_id if found, None otherwise.
    """
    for func_id, fcfg in functions.items():
        if node_id in fcfg.nodes:
            return func_id
    return None


def _deduplicate_calls(call_sites: List[CallSite]) -> List[CallSite]:
    """
    Deduplicate call edges.
    For calls inside loops, only keep one edge per (statement_id, callee_id) pair.
    This avoids creating redundant edges for loop iterations.
    """
    seen = {}
    unique_calls = []

    for cs in call_sites:
        # Use (statement_id, callee_id) as deduplication key
        key = (cs.statement_id, cs.callee_id)
        if key not in seen:
            seen[key] = cs
            unique_calls.append(cs)

    return unique_calls


def build_logic_graph(
    cfg: ControlFlowGraph,
    dug: DefUseGraph,
    index: AstIndex,
) -> LogicGraph:
    """
    Build a LogicGraph by combining CFG and def-use information.

    Args:
        cfg: Control flow graph
        dug: Definition-use graph
        index: AST index for node lookups

    Returns:
        A LogicGraph representing the high-level logical structure
    """
    # 1. Get statement nodes (module-level or main function)
    statement_nodes = set()
    control_flow_edges = {}
    entry_point_id = -1

    if cfg.module_cfg and cfg.module_cfg.nodes:
        # Use module-level code (Python, JavaScript)
        statement_nodes = set(cfg.module_cfg.nodes.keys())
        control_flow_edges = cfg.module_cfg.succ
        entry_point_id = -1
    else:
        # Try to find main function (C, Java)
        main_func_id = _find_main_function(cfg, index)
        if main_func_id is not None and main_func_id in cfg.functions:
            main_cfg = cfg.functions[main_func_id]
            statement_nodes = set(main_cfg.nodes.keys())
            control_flow_edges = main_cfg.succ
            entry_point_id = main_func_id
        else:
            # No entry point found, return empty graph
            return LogicGraph(
                statement_nodes=set(),
                data_edges=[],
                call_edges=[],
                function_call_edges=[],  # NEW!
                function_defs=dict(cfg.functions),
                entry_point=-1,
            )

    # 2. Build data dependency edges
    data_edges = _build_data_dependency_edges(
        control_flow_edges,
        statement_nodes,
        dug,
        index,
    )

    # 3. Classify and filter call edges
    # Separate into:
    # - Module/entry-level calls (including calls inside loops/ifs)
    # - Function-to-function calls
    entry_call_edges = []
    function_call_edges = []

    for cs in cfg.call_sites:
        # Skip unresolved calls
        if cs.callee_id is None:
            continue

        # Skip self-calls to entry point (e.g., main calling main)
        if cs.callee_id == entry_point_id:
            continue

        # Check where the call originates
        if cs.statement_id in statement_nodes:
            # Direct statement-level call
            entry_call_edges.append(cs)
        elif _is_descendant_of(cs.statement_id, statement_nodes, index):
            # Call inside a compound statement (loop/if) at module level
            entry_call_edges.append(cs)
        elif _is_in_function(cs.statement_id, cfg.functions):
            # Call from inside a function
            function_call_edges.append(cs)

    # 4. Deduplicate calls (handles loop iterations)
    entry_call_edges = _deduplicate_calls(entry_call_edges)
    function_call_edges = _deduplicate_calls(function_call_edges)

    # 5. Create function definitions map
    # If entry point is a function (not module level), exclude it from function_defs
    # to avoid showing main calling itself
    function_defs = dict(cfg.functions)
    if entry_point_id != -1 and entry_point_id in function_defs:
        function_defs = {fid: fcfg for fid, fcfg in function_defs.items() if fid != entry_point_id}

    # 6. Create LogicGraph
    logic_graph = LogicGraph(
        statement_nodes=statement_nodes,
        data_edges=data_edges,
        call_edges=entry_call_edges,
        function_call_edges=function_call_edges,  # NEW!
        function_defs=function_defs,
        entry_point=entry_point_id,
    )

    return logic_graph


def _build_data_dependency_edges(
    control_flow_edges: Dict[int, Set[int]],
    statement_nodes: Set[int],
    dug: DefUseGraph,
    index: AstIndex,
) -> List[DataDependencyEdge]:
    """
    Build data dependency edges by filtering control flow edges based on def-use.

    Only creates an edge if variables defined in the source are used in the target.
    """
    data_edges = []

    def get_all_descendants(node_id: int, index: AstIndex) -> Set[int]:
        """Get all descendant node IDs of a given node."""
        descendants = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            descendants.add(current)
            if current in index.children:
                queue.extend(index.children[current])
        return descendants

    # Process each control flow edge
    for src, dsts in control_flow_edges.items():
        if src not in statement_nodes:
            continue

        for dst in dsts:
            if dst not in statement_nodes:
                continue

            # Get all descendants of src and dst
            src_descendants = get_all_descendants(src, index)
            dst_descendants = get_all_descendants(dst, index)

            # Find all symbols defined in src statement
            src_defs = set()
            for def_id, symbols in dug.defs.items():
                if def_id in src_descendants:
                    src_defs.update(symbols)

            # Find all symbols used in dst statement
            dst_uses = set()
            for use_id, symbols in dug.uses.items():
                if use_id in dst_descendants:
                    dst_uses.update(symbols)

            # Check for data dependency
            # Handle cases like 'p' being used as 'p.shift'
            shared_symbols = set()
            for def_sym in src_defs:
                for use_sym in dst_uses:
                    # Direct match or use_sym starts with def_sym followed by '.'
                    if use_sym == def_sym or use_sym.startswith(def_sym + '.'):
                        shared_symbols.add(def_sym)

            # Create edge if there's a data dependency
            if shared_symbols:
                data_edges.append(DataDependencyEdge(
                    source_id=src,
                    target_id=dst,
                    shared_symbols=shared_symbols,
                ))

    return data_edges


# Re-export for convenience
__all__ = [
    'LogicGraph',
    'DataDependencyEdge',
    'build_logic_graph',
]
