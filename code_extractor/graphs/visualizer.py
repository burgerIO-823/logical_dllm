# code_extractor/graphs/visualizer.py

"""
Graph visualization module for CFG and Def-Use graphs.

This module provides functions to visualize:
- Control Flow Graphs (CFG)
- Definition-Use (Def-Use) graphs

It uses graphviz for rendering, with fallback to text-based visualization.
"""

from __future__ import annotations
from typing import Optional, Dict, Set
from pathlib import Path

try:
    import graphviz
    GRAPHVIZ_AVAILABLE = True
except ImportError:
    GRAPHVIZ_AVAILABLE = False

from code_extractor.graphs.cfg import ControlFlowGraph
from code_extractor.graphs.def_use import DefUseGraph
from code_extractor.graphs.ast_index import AstIndex


# =========================
#   CFG Visualization
# =========================

def _truncate_text(text: str, max_len: int = 40) -> str:
    """Truncate text and replace newlines for node labels."""
    text = text.replace("\n", "\\n")
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def visualize_cfg(
    cfg: ControlFlowGraph,
    index: AstIndex,
    output_path: Optional[str] = None,
    format: str = "png",
    view: bool = False,
    max_functions: Optional[int] = None,
    show_call_edges: bool = True,
    view_mode: str = "simple",
) -> Optional[str]:
    """
    Visualize a Control Flow Graph using graphviz.

    Args:
        cfg: The ControlFlowGraph to visualize
        index: AstIndex for looking up node information
        output_path: Path to save the output file (without extension)
                    If None, generates a default name based on timestamp
        format: Output format (png, pdf, svg, etc.)
        view: Whether to open the rendered graph automatically
        max_functions: Maximum number of functions to visualize (None = all)
        show_call_edges: Whether to show function call relationships (default: True)
        view_mode: Visualization mode - "simple" (top-bottom layout) or "detailed" (full CFG)

    Returns:
        Path to the generated file, or None if graphviz is not available
    """
    if not GRAPHVIZ_AVAILABLE:
        print("Warning: graphviz not installed. Use: pip install graphviz")
        print("Falling back to text visualization...")
        visualize_cfg_text(cfg, index, max_functions=max_functions)
        return None

    if view_mode == "detailed":
        return _visualize_cfg_detailed(cfg, index, output_path, format, view, max_functions, show_call_edges)
    else:
        # Build logic graph combining CFG and def-use
        from code_extractor.graphs.def_use import build_def_use
        from code_extractor.graphs.logic_graph import build_logic_graph
        dug = build_def_use(index)
        logic_graph = build_logic_graph(cfg, dug, index)
        return _visualize_logic_graph(logic_graph, index, output_path, format, view, max_functions)


def _visualize_cfg_detailed(
    cfg: ControlFlowGraph,
    index: AstIndex,
    output_path: Optional[str],
    format: str,
    view: bool,
    max_functions: Optional[int],
    show_call_edges: bool,
) -> Optional[str]:
    """Detailed view with full CFG expanded for each function."""
    # Create main graph
    dot = graphviz.Digraph(
        name="CFG",
        comment="Enhanced Control Flow Graph with Call Relationships",
        format=format,
    )
    dot.attr(rankdir="TB")  # Top to Bottom layout
    dot.attr("node", shape="box", style="rounded,filled", fillcolor="lightblue")
    dot.attr("edge", color="black")

    # 1) Add module-level CFG if exists
    if cfg.module_cfg:
        with dot.subgraph(name="cluster_module") as sub:
            sub.attr(label="Module Level (Global Scope)", style="filled", color="lightyellow")

            # Add module nodes
            for node_id in cfg.module_cfg.nodes:
                node = index.nodes_by_id.get(node_id)
                if node:
                    label = f"id:{node_id}\\n{node.kind}\\n{_truncate_text(node.text, 30)}"
                else:
                    label = f"id:{node_id}"
                sub.node(f"n_{node_id}", label=label, fillcolor="lightyellow")

            # Add module edges
            for src, dsts in cfg.module_cfg.succ.items():
                for dst in dsts:
                    sub.edge(f"n_{src}", f"n_{dst}")

    # 2) Process each function
    func_items = list(cfg.functions.items())
    if max_functions is not None:
        func_items = func_items[:max_functions]

    for func_id, fcfg in func_items:
        func_node = index.nodes_by_id.get(func_id)
        func_name = _truncate_text(func_node.text.strip(), 30) if func_node else f"func_{func_id}"

        # Create subgraph for this function
        with dot.subgraph(name=f"cluster_{func_id}") as sub:
            sub.attr(label=f"Function: {func_name}", style="filled", color="lightgrey")

            # Add function entry node
            sub.node(
                f"fn_{func_id}",
                label=f"ENTRY\\n{func_name}",
                shape="ellipse",
                fillcolor="lightgreen",
            )

            # Add CFG nodes
            for node_id in fcfg.nodes:
                node = index.nodes_by_id.get(node_id)
                if node:
                    label = f"id:{node_id}\\n{node.kind}\\n{_truncate_text(node.text, 30)}"
                else:
                    label = f"id:{node_id}"

                # Color exit nodes differently
                if node_id in fcfg.exits:
                    sub.node(f"n_{node_id}", label=label, fillcolor="lightcoral")
                else:
                    sub.node(f"n_{node_id}", label=label)

            # Add edges
            for src, dsts in fcfg.succ.items():
                for dst in dsts:
                    # Handle edge from function entry
                    src_name = f"fn_{func_id}" if src == func_id else f"n_{src}"
                    dst_name = f"n_{dst}"
                    sub.edge(src_name, dst_name)

    # 3) Add function call edges (cross-cluster edges) - DISABLED
    # In detailed CFG view, we focus on control flow within functions
    # and don't show cross-function call edges to avoid clutter
    # if show_call_edges and cfg.call_edges:
    #     for caller_id, callee_id, call_site_id in cfg.call_edges:
    #         # Determine source node name
    #         if caller_id == -1:
    #             # Call from module level
    #             src_name = f"n_{call_site_id}"
    #         else:
    #             # Call from within a function
    #             src_name = f"n_{call_site_id}"
    #
    #         # Target is the function entry node
    #         dst_name = f"fn_{callee_id}"
    #
    #         # Add call edge with distinct style
    #         dot.edge(
    #             src_name,
    #             dst_name,
    #             label="call",
    #             color="red",
    #             style="dashed",
    #             constraint="false",  # Don't affect layout too much
    #         )

    # Save and optionally view
    if output_path is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"cfg_{timestamp}"

    output_file = dot.render(output_path, view=view, cleanup=True)
    print(f"Enhanced CFG visualization saved to: {output_file}")
    return output_file


def _visualize_logic_graph(
    logic_graph: 'LogicGraph',
    index: AstIndex,
    output_path: Optional[str],
    format: str,
    view: bool,
    max_functions: Optional[int],
) -> Optional[str]:
    """
    Visualize a LogicGraph with top-bottom layout:
    - TOP: Module-level code (statements)
    - BOTTOM: Simplified function definition nodes
    - Black arrows: Data dependency edges
    - Red arrows: Function call edges
    """
    from code_extractor.graphs.logic_graph import LogicGraph
    dot = graphviz.Digraph(
        name="CFG_Simple",
        comment="Simple Top-Bottom CFG View",
        format=format,
    )
    dot.attr(rankdir="TB")  # Top to Bottom
    dot.attr("node", shape="box", style="rounded,filled")
    dot.attr(nodesep="0.5")
    dot.attr(ranksep="1.0")

    # Collect function info
    func_items = list(logic_graph.function_defs.items())
    if max_functions is not None:
        func_items = func_items[:max_functions]

    # === TOP: Module-Level Code ===
    if logic_graph.statement_nodes:
        with dot.subgraph(name="cluster_module") as module:
            module.attr(label="📍 Module Level (Entry Point)",
                       style="filled", color="lightyellow",
                       fontsize="14", fontname="Arial Bold")

            # Add each statement as a node
            for node_id in sorted(logic_graph.statement_nodes):
                node = index.nodes_by_id.get(node_id)
                if node:
                    stmt_text = _truncate_text(node.text.strip(), 40)
                    module.node(f"stmt_{node_id}", label=stmt_text,
                               fillcolor="lightyellow", fontname="Courier",
                               fontsize="10", shape="box")

            # Add data dependency edges (from LogicGraph)
            for edge in logic_graph.data_edges:
                module.edge(f"stmt_{edge.source_id}", f"stmt_{edge.target_id}",
                           color="black", arrowsize="0.7")

    # === BOTTOM: Function Definitions (Detailed with Internal Structure) ===
    for func_id, fcfg in func_items:
        func_node = index.nodes_by_id.get(func_id)
        if func_node:
            # Get function signature (first line)
            lines = func_node.text.strip().split('\n')
            sig = lines[0].strip() if lines else "unknown"
            # Clean signature - remove type keywords
            for kw in ['void ', 'int ', 'Point ', 'double ', 'float ',
                      'static ', 'public ', 'private ', 'class ']:
                sig = sig.replace(kw, '')
            func_label = f"🔧 Function: {sig}"
        else:
            func_label = f"🔧 Function: func_{func_id}"

        # Create a subgraph for each function showing internal structure
        with dot.subgraph(name=f"cluster_func_{func_id}") as func_cluster:
            func_cluster.attr(label=func_label,
                            style="filled", color="lightblue",
                            fontsize="12", fontname="Arial")

            # Add function entry/header node
            func_cluster.node(f"fn_{func_id}", label=f"ENTRY\\n{sig}",
                            fillcolor="lightgreen", shape="ellipse",
                            fontname="Courier", fontsize="9")

            # Add internal statement nodes
            for stmt_id in fcfg.nodes:
                stmt_node = index.nodes_by_id.get(stmt_id)
                if stmt_node:
                    stmt_text = _truncate_text(stmt_node.text.strip(), 35)
                    # Color return statements differently
                    if 'return' in stmt_node.text.lower():
                        fill_color = "lightcoral"
                    else:
                        fill_color = "lightblue"
                else:
                    stmt_text = f"stmt_{stmt_id}"
                    fill_color = "lightblue"

                func_cluster.node(f"fn_{func_id}_stmt_{stmt_id}",
                                label=stmt_text,
                                fillcolor=fill_color,
                                shape="box",
                                fontname="Courier",
                                fontsize="9")

            # Add enhanced edges (merged control flow + data flow)
            for edge in fcfg.enhanced_edges:
                src_name = f"fn_{func_id}" if edge.source_id == func_id else f"fn_{func_id}_stmt_{edge.source_id}"
                dst_name = f"fn_{func_id}_stmt_{edge.target_id}"

                # Determine edge style based on what it represents
                if edge.has_control_flow and edge.has_data_flow:
                    # Both control and data: dark blue bold line with variable labels
                    edge_label = ", ".join(list(edge.shared_symbols)[:2])
                    if len(edge.shared_symbols) > 2:
                        edge_label += "..."
                    func_cluster.edge(src_name, dst_name,
                                    label=edge_label,
                                    color="darkblue", style="bold",
                                    fontcolor="darkblue", fontsize="8",
                                    arrowsize="0.8", penwidth="2.5")
                elif edge.has_data_flow:
                    # Data only (rare, cross-path dependency): green dashed line
                    edge_label = ", ".join(list(edge.shared_symbols)[:2])
                    if len(edge.shared_symbols) > 2:
                        edge_label += "..."
                    func_cluster.edge(src_name, dst_name,
                                    label=edge_label,
                                    color="green", style="dashed",
                                    fontcolor="darkgreen", fontsize="8",
                                    arrowsize="0.7", penwidth="2.0")
                else:
                    # Control only: grey thin line
                    func_cluster.edge(src_name, dst_name,
                                    color="grey", style="solid",
                                    arrowsize="0.6", penwidth="1.0")

    # === Call Edges: From statements to function definitions ===
    for call_site in logic_graph.call_edges:
        # Find the actual source statement to display
        stmt_id = call_site.statement_id

        # If the statement is not in statement_nodes (e.g., inside a loop),
        # find its parent that IS in statement_nodes
        if stmt_id not in logic_graph.statement_nodes:
            current = stmt_id
            while current is not None:
                parent = index.parent.get(current)
                if parent and parent in logic_graph.statement_nodes:
                    stmt_id = parent
                    break
                current = parent

        # Source: the (possibly mapped) statement
        src = f"stmt_{stmt_id}"

        # Target: the function definition
        dst = f"fn_{call_site.callee_id}"

        # Draw call edge (red solid arrow)
        dot.edge(src, dst,
                label=call_site.callee_name,
                color="red", style="bold",
                fontcolor="red", fontsize="10",
                penwidth="2.0")

    # === Function-to-Function Call Edges (NEW) ===
    for call_site in logic_graph.function_call_edges:
        # Find which function contains this call
        caller_func_id = None
        for func_id, fcfg in logic_graph.function_defs.items():
            if call_site.statement_id in fcfg.nodes:
                caller_func_id = func_id
                break

        # If we found the caller function, draw the edge
        if caller_func_id is not None:
            src = f"fn_{caller_func_id}"
            dst = f"fn_{call_site.callee_id}"

            # Draw function-to-function edge (blue dashed arrow)
            dot.edge(src, dst,
                    label=call_site.callee_name,
                    color="blue", style="dashed",
                    fontcolor="blue", fontsize="9",
                    penwidth="1.5",
                    constraint="false")  # Don't affect layout

    # Save
    if output_path is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"cfg_simple_{timestamp}"

    output_file = dot.render(output_path, view=view, cleanup=True)
    print(f"CFG simple visualization saved to: {output_file}")
    return output_file


def visualize_cfg_text(
    cfg: ControlFlowGraph,
    index: AstIndex,
    max_functions: Optional[int] = None,
    max_edges_per_func: int = 20,
) -> None:
    """
    Text-based visualization of CFG (fallback when graphviz is not available).

    Args:
        cfg: The ControlFlowGraph to visualize
        index: AstIndex for looking up node information
        max_functions: Maximum number of functions to show
        max_edges_per_func: Maximum edges to display per function
    """
    print("\n" + "=" * 80)
    print("ENHANCED CONTROL FLOW GRAPH (Text View)")
    print("=" * 80)

    # Show module-level CFG if exists
    if cfg.module_cfg:
        print(f"\n{'─' * 80}")
        print("Module Level (Global Scope)")
        print(f"  Entry: {cfg.module_cfg.entry}")
        print(f"  Exits: {sorted(cfg.module_cfg.exits) if cfg.module_cfg.exits else []}")
        print(f"  Nodes: {len(cfg.module_cfg.nodes)}")

        edges = []
        for src, dsts in cfg.module_cfg.succ.items():
            for dst in dsts:
                edges.append((src, dst))

        print(f"  Edges: {len(edges)}")
        if edges:
            print(f"\n  Module-level flow:")
            for i, (src, dst) in enumerate(edges):
                if i >= max_edges_per_func:
                    print(f"    ... ({len(edges) - max_edges_per_func} more)")
                    break
                src_node = index.nodes_by_id.get(src)
                dst_node = index.nodes_by_id.get(dst)
                src_preview = src_node.text.replace("\n", " ")[:40] if src_node else "<?>"
                dst_preview = dst_node.text.replace("\n", " ")[:40] if dst_node else "<?>"
                print(f"    {src:3d} -> {dst:3d}")
                print(f"        src: {src_preview}")
                print(f"        dst: {dst_preview}")

    if not cfg.functions:
        if not cfg.module_cfg:
            print("CFG is empty (no functions or module code found).")
        print("\n" + "=" * 80)
        return

    func_items = list(cfg.functions.items())
    if max_functions is not None:
        func_items = func_items[:max_functions]

    for func_id, fcfg in func_items:
        func_node = index.nodes_by_id.get(func_id)
        func_name = (func_node.text.strip() if func_node else f"<id {func_id}>")[:50]

        print(f"\n{'─' * 80}")
        print(f"Function: {func_name}")
        print(f"  ID: {func_id}")
        print(f"  Entry: {fcfg.entry}")
        print(f"  Exits: {sorted(fcfg.exits) if fcfg.exits else []}")
        print(f"  Nodes: {len(fcfg.nodes)}")

        # Collect edges
        edges = []
        for src, dsts in fcfg.succ.items():
            for dst in dsts:
                edges.append((src, dst))

        print(f"  Edges: {len(edges)}")
        print(f"\n  Control flow edges:")
        for i, (src, dst) in enumerate(edges):
            if i >= max_edges_per_func:
                print(f"    ... ({len(edges) - max_edges_per_func} more)")
                break

            src_node = index.nodes_by_id.get(src)
            dst_node = index.nodes_by_id.get(dst)

            src_preview = src_node.text.replace("\n", " ")[:40] if src_node else "<?>"
            dst_preview = dst_node.text.replace("\n", " ")[:40] if dst_node else "<?>"

            print(f"    {src:3d} -> {dst:3d}")
            print(f"        src: {src_preview}")
            print(f"        dst: {dst_preview}")

    # Show function call relationships
    if cfg.call_edges:
        print(f"\n{'─' * 80}")
        print(f"Function Call Relationships ({len(cfg.call_edges)} calls)")
        print("─" * 80)
        for caller_id, callee_id, call_site_id in cfg.call_edges:
            caller_name = "Module" if caller_id == -1 else f"Function {caller_id}"
            callee_node = index.nodes_by_id.get(callee_id)
            callee_name = callee_node.text.strip()[:40] if callee_node else f"Function {callee_id}"
            call_node = index.nodes_by_id.get(call_site_id)
            call_text = call_node.text.replace("\n", " ")[:40] if call_node else "<?>"
            print(f"  {caller_name} -> {callee_name}")
            print(f"      at: {call_text}")

    print("\n" + "=" * 80)


# =========================
#   Def-Use Visualization
# =========================

def visualize_def_use(
    dug: DefUseGraph,
    index: AstIndex,
    output_path: Optional[str] = None,
    format: str = "png",
    view: bool = False,
    max_edges: Optional[int] = None,
    show_isolated_nodes: bool = True,
) -> Optional[str]:
    """
    Visualize a Definition-Use Graph using graphviz.

    Args:
        dug: The DefUseGraph to visualize
        index: AstIndex for looking up node information
        output_path: Path to save the output file (without extension)
        format: Output format (png, pdf, svg, etc.)
        view: Whether to open the rendered graph automatically
        max_edges: Maximum number of edges to show (None = all)
        show_isolated_nodes: Whether to show nodes with no edges

    Returns:
        Path to the generated file, or None if graphviz is not available
    """
    if not GRAPHVIZ_AVAILABLE:
        print("Warning: graphviz not installed. Use: pip install graphviz")
        print("Falling back to text visualization...")
        visualize_def_use_text(dug, index, max_edges=max_edges)
        return None

    # Create graph
    dot = graphviz.Digraph(
        name="DefUse",
        comment="Definition-Use Graph",
        format=format,
    )
    dot.attr(rankdir="LR")  # Left to Right layout
    dot.attr("node", shape="box", style="rounded,filled")
    dot.attr("edge", color="blue", fontsize="10")

    # Collect all nodes involved in edges
    nodes_with_edges: Set[int] = set()
    for def_id, use_id, symbol in dug.edges:
        nodes_with_edges.add(def_id)
        nodes_with_edges.add(use_id)

    # Add definition nodes
    for node_id, symbols in dug.defs.items():
        if not show_isolated_nodes and node_id not in nodes_with_edges:
            continue

        node = index.nodes_by_id.get(node_id)
        if node:
            text_preview = _truncate_text(node.text, 25)
            label = f"DEF {node_id}\\n{', '.join(sorted(symbols))}\\n{text_preview}"
        else:
            label = f"DEF {node_id}\\n{', '.join(sorted(symbols))}"

        dot.node(f"def_{node_id}", label=label, fillcolor="lightgreen")

    # Add use nodes
    for node_id, symbols in dug.uses.items():
        if not show_isolated_nodes and node_id not in nodes_with_edges:
            continue

        node = index.nodes_by_id.get(node_id)
        if node:
            text_preview = _truncate_text(node.text, 25)
            label = f"USE {node_id}\\n{', '.join(sorted(symbols))}\\n{text_preview}"
        else:
            label = f"USE {node_id}\\n{', '.join(sorted(symbols))}"

        dot.node(f"use_{node_id}", label=label, fillcolor="lightcoral")

    # Add edges
    edges = dug.edges if max_edges is None else dug.edges[:max_edges]
    for def_id, use_id, symbol in edges:
        dot.edge(f"def_{def_id}", f"use_{use_id}", label=symbol)

    if max_edges is not None and len(dug.edges) > max_edges:
        # Add note about truncated edges
        dot.node(
            "note",
            label=f"... {len(dug.edges) - max_edges} more edges",
            shape="plaintext",
            fillcolor="white",
        )

    # Save and optionally view
    if output_path is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"defuse_{timestamp}"

    output_file = dot.render(output_path, view=view, cleanup=True)
    print(f"Def-Use visualization saved to: {output_file}")
    return output_file


def visualize_def_use_text(
    dug: DefUseGraph,
    index: AstIndex,
    max_edges: Optional[int] = 50,
) -> None:
    """
    Text-based visualization of Def-Use graph.

    Args:
        dug: The DefUseGraph to visualize
        index: AstIndex for looking up node information
        max_edges: Maximum number of edges to display
    """
    print("\n" + "=" * 80)
    print("DEFINITION-USE GRAPH (Text View)")
    print("=" * 80)

    # Definitions
    print(f"\nDefinitions ({len(dug.defs)} nodes):")
    print("─" * 80)
    for nid, symbols in sorted(dug.defs.items()):
        node = index.nodes_by_id.get(nid)
        if node:
            preview = node.text.replace("\n", " ")[:40]
            print(f"  [DEF {nid:3d}] {', '.join(sorted(symbols)):20s} | {node.kind:12s} | {preview}")
        else:
            print(f"  [DEF {nid:3d}] {', '.join(sorted(symbols))}")

    # Uses
    print(f"\nUses ({len(dug.uses)} nodes):")
    print("─" * 80)
    for nid, symbols in sorted(dug.uses.items()):
        node = index.nodes_by_id.get(nid)
        if node:
            preview = node.text.replace("\n", " ")[:40]
            print(f"  [USE {nid:3d}] {', '.join(sorted(symbols)):20s} | {node.kind:12s} | {preview}")
        else:
            print(f"  [USE {nid:3d}] {', '.join(sorted(symbols))}")

    # Edges
    edges = dug.edges if max_edges is None else dug.edges[:max_edges]
    print(f"\nDef-Use Edges ({len(dug.edges)} total, showing {len(edges)}):")
    print("─" * 80)
    for def_id, use_id, symbol in edges:
        def_node = index.nodes_by_id.get(def_id)
        use_node = index.nodes_by_id.get(use_id)

        def_preview = def_node.text.replace("\n", " ")[:30] if def_node else "<?>"
        use_preview = use_node.text.replace("\n", " ")[:30] if use_node else "<?>"

        print(f"  {symbol:15s}: DEF[{def_id:3d}] -> USE[{use_id:3d}]")
        print(f"      def: {def_preview}")
        print(f"      use: {use_preview}")

    if max_edges is not None and len(dug.edges) > max_edges:
        print(f"  ... ({len(dug.edges) - max_edges} more edges)")

    print("\n" + "=" * 80)


# =========================
#   Combined Visualization
# =========================

def visualize_all(
    cfg: ControlFlowGraph,
    dug: DefUseGraph,
    index: AstIndex,
    output_dir: str = ".",
    format: str = "png",
    view: bool = False,
) -> Dict[str, Optional[str]]:
    """
    Visualize both CFG and Def-Use graphs.

    Args:
        cfg: ControlFlowGraph to visualize
        dug: DefUseGraph to visualize
        index: AstIndex for node lookups
        output_dir: Directory to save output files
        format: Output format
        view: Whether to open rendered graphs

    Returns:
        Dictionary with paths to generated files
    """
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    results = {}

    # Visualize CFG
    cfg_path = str(output_dir_path / f"cfg_{timestamp}")
    results["cfg"] = visualize_cfg(cfg, index, cfg_path, format, view)

    # Visualize Def-Use
    defuse_path = str(output_dir_path / f"defuse_{timestamp}")
    results["defuse"] = visualize_def_use(dug, index, defuse_path, format, view)

    return results
