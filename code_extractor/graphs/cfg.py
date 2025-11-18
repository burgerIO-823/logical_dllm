# code_extractor/graphs/cfg.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict

from code_extractor.parsers.ast import AstNodeRec
from code_extractor.graphs.ast_index import AstIndex


# 哪些 kind 视为“语句级节点”
STMT_KINDS: Set[str] = {
    "assignment",
    "if_stmt",
    "loop_stmt",
    "return_stmt",
    "call_expr",      # 顶层调用语句（通常出现在 expression_statement 等 wrapper 下面）
}


@dataclass
class FunctionCFG:
    """
    控制流图的一份 function-level 视图。

    - nodes:      参与控制流的 AST node_id -> AstNodeRec
    - succ / pred: 控制流有向边
    - entry:      入口语句（通常是函数体里的第一条语句；如果函数体为空则为 None）
    - exits:      可能的出口语句（当前简化版，只是“在函数体内没有后继的语句”）
    """
    func_id: int
    entry: Optional[int]
    exits: Set[int] = field(default_factory=set)
    nodes: Dict[int, AstNodeRec] = field(default_factory=dict)
    succ: Dict[int, List[int]] = field(default_factory=lambda: defaultdict(list))
    pred: Dict[int, List[int]] = field(default_factory=lambda: defaultdict(list))


@dataclass
class ControlFlowGraph:
    """
    整个文件 / 模块级别的 CFG 汇总。
    目前只按 function_def 粒度切分，每个函数对应一个 FunctionCFG。
    """
    functions: Dict[int, FunctionCFG] = field(default_factory=dict)


# ============ 小工具函数 ============

def _is_stmt_node(node: AstNodeRec) -> bool:
    """当前版本里视为 CFG 节点的 AST kind。"""
    return node.kind in STMT_KINDS


def _collect_block_statements(block_id: int, index: AstIndex) -> List[int]:
    """
    在一个 block 节点下，按出现顺序收集“语句级”子节点的 id。

    规则：
      - 如果子节点本身就是 STMT_KINDS -> 直接收集
      - 如果子节点是 wrapper（kind == "other"），往下一层寻找第一个
        属于 STMT_KINDS 的孩子，并按顺序收集
    """
    nodes = index.nodes_by_id
    children = index.children

    result: List[int] = []

    for cid in children.get(block_id, []):
        child = nodes[cid]

        if _is_stmt_node(child):
            result.append(cid)
            continue

        if child.kind == "other":
            # 在 wrapper 下面找语句级孩子
            for gcid in children.get(cid, []):
                gchild = nodes[gcid]
                if _is_stmt_node(gchild):
                    result.append(gcid)
                    # 一般一个 wrapper 里只有一条主语句，找到第一条就 break
                    break

    return result


def _find_function_body_block(fn_id: int, index: AstIndex) -> Optional[int]:
    """
    找到 function_def 节点对应的“主体 block”。
    - Python: function_definition -> block
    - JS: method_declaration / function_declaration -> statement_block
    - C: function_definition -> compound_statement
    - Java: method_declaration / constructor_declaration -> block
    归一后这些都被 normalize 成 kind == "block" 了。
    """
    nodes = index.nodes_by_id
    children = index.children

    for cid in children.get(fn_id, []):
        if nodes[cid].kind == "block":
            return cid
    return None


def _connect(cfg: FunctionCFG, src: int, dst: int) -> None:
    """在 CFG 中添加一条 src -> dst 的控制流边（避免重复边也可以后面加去重）。"""
    cfg.succ[src].append(dst)
    cfg.pred[dst].append(src)
    # 把节点放进 nodes 映射，方便后面查 kind / 文本
    if src not in cfg.nodes:
        cfg.nodes[src] = cfg.nodes_all[src]
    if dst not in cfg.nodes:
        cfg.nodes[dst] = cfg.nodes_all[dst]


def _build_sequence_edges(
    cfg: FunctionCFG,
    stmt_ids: List[int],
    index: AstIndex,
    incoming: List[int],
) -> List[int]:
    """
    在同一层 block 内，按顺序给 stmt_ids 建立控制流边。

    参数：
      - stmt_ids: 当前 block 里的语句节点 id（已按顺序）
      - incoming: 来自上一层/前置语句的“入口节点集合”，需要连到本序列的第一条语句。

    返回：
      - 本序列的“出口候选集合”：顺序中最后一条语句的 id（如果存在）
        + 其中一些语句可能因为 if 分支等情况产生额外出口，后续再扩展。
      当前简化版里，我们只返回 [最后一条语句] 或 incoming（当 stmt_ids 为空）。
    """
    if not stmt_ids:
        # 空 block：出口就是入口（控制流直接穿过）
        return incoming

    # 1) 入口 -> 第一条语句
    first_stmt = stmt_ids[0]
    for src in incoming:
        _connect(cfg, src, first_stmt)

    # 2) 顺序执行：Si -> S(i+1)
    for i in range(len(stmt_ids) - 1):
        cur_id = stmt_ids[i]
        next_id = stmt_ids[i + 1]
        _connect(cfg, cur_id, next_id)

    # 3) 简化版 if/loop 处理在后面迭代中可加入，目前只做线性顺序
    #    如果想立即加 “if -> then_block 首语句”，可以在这里
    #    识别 kind == "if_stmt" 再额外添加边。
    #
    #    这里先返回顺序最后一条语句作为“出口候选”。
    return [stmt_ids[-1]]


# ============ 核心：构建单个函数的 CFG ============

def build_function_cfg(fn_id: int, index: AstIndex) -> FunctionCFG:
    """
    从一个 function_def 节点出发，构建它的控制流图（简化版）。

    当前版本：
      - 把函数体 block 内的语句串成一条线性控制流
      - 还没有精细处理 if / loop 的分支和回边
    """
    nodes = index.nodes_by_id

    cfg = FunctionCFG(
        func_id=fn_id,
        entry=None,
    )
    # 临时保存所有 AST 节点，_connect 时用来填充 cfg.nodes
    cfg.nodes_all = nodes  # 动态挂个属性，用完就可以不理它了

    body_block = _find_function_body_block(fn_id, index)
    if body_block is None:
        # 空函数：无 entry/exit
        return cfg

    # 收集函数体内（顶层 block）的语句列表
    stmts = _collect_block_statements(body_block, index)
    if not stmts:
        return cfg

    cfg.entry = stmts[0]

    # 入口来自“函数头”本身，也可以看作一个 pseudo entry node
    # 这里简单地：fn_id -> 第一条语句
    _connect(cfg, fn_id, stmts[0])

    # 构建线性顺序边
    exits = _build_sequence_edges(cfg, stmts, index, incoming=[fn_id])
    cfg.exits = set(exits)

    # 清理掉临时字段
    del cfg.nodes_all
    return cfg


# ============ 顶层：整个文件 / 模块的 CFG ============

def build_cfg(index: AstIndex) -> ControlFlowGraph:
    """
    从 AstIndex 构建整个文件/模块级别的 CFG。

    策略：
      - 遍历所有 AST 节点，找到 kind == "function_def" 的节点
      - 对每个函数分别调用 build_function_cfg
    """
    cfg = ControlFlowGraph()
    nodes = index.nodes_by_id

    for nid, node in nodes.items():
        if node.kind == "function_def":
            func_cfg = build_function_cfg(nid, index)
            cfg.functions[nid] = func_cfg

    return cfg