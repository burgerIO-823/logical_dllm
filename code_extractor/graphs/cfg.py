# code_extractor/graphs/cfg.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Any
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
class CallSite:
    """
    表示一个函数调用点的详细信息
    """
    call_node_id: int           # call_expr节点ID
    caller_context_id: int      # 调用者上下文（函数ID或-1表示模块）
    callee_name: str           # 被调用函数名
    callee_id: Optional[int]   # 被调用函数的节点ID（如果能解析到）
    statement_id: int          # 包含此调用的语句ID


@dataclass
class ControlFlowGraph:
    """
    增强的控制流图，重点展示调用关系和执行流。

    核心概念：
    - 区分"定义"和"调用"
    - 构建从主入口点开始的调用树
    - 展示层次化的执行流程

    字段：
    - functions: 函数定义的CFG（工具函数/库代码）
    - module_cfg: 模块级CFG（主执行逻辑）
    - call_sites: 所有调用点的详细信息
    - entry_points: 主入口点列表（模块级或main函数）
    - call_tree: 调用树结构（从入口点展开）
    """
    functions: Dict[int, FunctionCFG] = field(default_factory=dict)
    module_cfg: Optional[FunctionCFG] = None
    call_sites: List[CallSite] = field(default_factory=list)
    entry_points: List[int] = field(default_factory=list)  # 入口点ID列表
    call_edges: List[Tuple[int, int, int]] = field(default_factory=list)  # 保留向后兼容


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


# ============ 辅助函数：增强的调用识别 ============

def _find_all_calls_in_node(node_id: int, index: AstIndex) -> List[Tuple[int, int]]:
    """
    在给定节点中查找所有call_expr，并返回(call_id, statement_id)对。
    statement_id是包含这个调用的语句节点。
    """
    nodes = index.nodes_by_id
    children = index.children
    parent = index.parent
    calls = []

    def find_statement_ancestor(nid: int) -> int:
        """
        找到包含此节点的语句节点。
        如果节点本身是call_expr，则跳过它继续向上查找，
        因为我们想要找到包含这个调用的更高层语句（如assignment）。
        """
        current = parent.get(nid)  # 从父节点开始（跳过call_expr自己）
        while current is not None:
            node = nodes.get(current)
            if node and _is_stmt_node(node):
                return current
            current = parent.get(current)
        return nid  # 如果找不到父语句，返回调用节点自己

    def dfs(nid: int):
        node = nodes.get(nid)
        if node and node.kind == "call_expr":
            stmt_id = find_statement_ancestor(nid)
            calls.append((nid, stmt_id))
        for cid in children.get(nid, []):
            dfs(cid)

    dfs(node_id)
    return calls


def _extract_call_info(call_id: int, index: AstIndex) -> Tuple[Optional[str], Optional[str]]:
    """
    从call_expr提取完整的调用信息。
    返回: (function_name, full_call_text)

    处理情况：
    - Point(1, 2) -> ("Point", "Point")
    - p.shift(3, 4) -> ("shift", "p.shift")  [Java/C++方法调用]
    - new Point(1, 2) -> ("Point", "new Point")  [构造函数]
    - obj.method() -> ("method", "obj.method")
    """
    nodes = index.nodes_by_id
    children = index.children

    # 获取完整文本
    call_node = nodes.get(call_id)
    full_text = call_node.text.strip() if call_node else None

    # 收集所有identifier子节点
    identifiers = []
    for cid in children.get(call_id, []):
        child = nodes[cid]
        if child.kind == "identifier":
            identifiers.append(child.text.strip())
        elif child.kind == "attr_access":
            # 对于 p.shift()，提取 shift 作为函数名
            text = child.text.strip()
            if '.' in text:
                func_name = text.split('.')[-1]
                return (func_name, text)
            elif '->' in text:
                func_name = text.split('->')[-1]
                return (func_name, text)
            return (text, text)
        elif child.kind == "other":
            # 对于 new Point()，'other'节点可能包含类名
            text = child.text.strip()
            # 移除参数列表
            if '(' in text:
                text = text.split('(')[0].strip()
            if text and not text.startswith('('):
                # 这可能是构造函数名或其他调用目标
                identifiers.append(text)

    # 如果有多个identifier（如 p.shift），使用最后一个（方法名）
    if len(identifiers) > 1:
        return (identifiers[-1], '.'.join(identifiers))
    elif len(identifiers) == 1:
        return (identifiers[0], identifiers[0])

    return (None, full_text)


def _is_if_main_block(node_id: int, index: AstIndex) -> bool:
    """
    检查节点是否是 `if __name__ == "__main__":` 块。
    """
    node = index.nodes_by_id.get(node_id)
    if not node or node.kind != "if_stmt":
        return False

    # 检查条件部分是否包含 __name__ 和 __main__
    text = node.text.lower()
    return '__name__' in text and '__main__' in text and '==' in text


def _find_module_level_statements(index: AstIndex) -> List[int]:
    """
    查找模块级别（不在任何函数内）的语句节点。
    对于 `if __name__ == "__main__":` 块，提取其内部的语句。
    返回这些语句的ID列表。
    """
    nodes = index.nodes_by_id
    parent = index.parent

    # 找到所有根节点
    root_ids = [nid for nid, p in parent.items() if p is None]
    if not root_ids:
        return []

    module_stmts = []

    # 从根节点开始，查找直接子节点中的语句
    def collect_top_level_stmts(nid: int, in_function: bool = False):
        node = nodes[nid]

        # 如果进入函数，标记in_function=True
        if node.kind == "function_def" or node.kind == "class_def":
            in_function = True

        # 如果是语句且不在函数内
        if not in_function and _is_stmt_node(node):
            # 特殊处理：if __name__ == "__main__": 块
            if _is_if_main_block(nid, index):
                # 提取块内的语句，而不是if语句本身
                # 找到block节点（if的body）
                for cid in index.children.get(nid, []):
                    child = nodes[cid]
                    if child.kind == "block":
                        # 收集block内的所有语句
                        block_stmts = _collect_block_statements(cid, index)
                        module_stmts.extend(block_stmts)
                        return
                # 如果没找到block，回退到默认行为
                module_stmts.append(nid)
            else:
                # 普通语句，直接添加
                module_stmts.append(nid)
            return  # 不再递归到子节点

        # 递归处理子节点
        for cid in index.children.get(nid, []):
            collect_top_level_stmts(cid, in_function)

    for rid in root_ids:
        collect_top_level_stmts(rid)

    return module_stmts


# ============ 顶层：整个文件 / 模块的 CFG ============

def build_cfg(index: AstIndex) -> ControlFlowGraph:
    """
    构建增强的CFG，重点展示调用关系和执行流。

    新方法：
    1. 构建所有函数的CFG（定义）
    2. 构建模块级CFG（主逻辑）
    3. 识别所有调用点（包括构造函数、方法调用）
    4. 确定主入口点
    5. 构建调用关系
    """
    cfg = ControlFlowGraph()
    nodes = index.nodes_by_id
    children = index.children

    # 1) 先收集类名到构造函数的映射
    class_name_to_init: Dict[str, int] = {}  # 类名 -> 构造函数ID

    # 首先找到所有类定义
    for nid, node in nodes.items():
        if node.kind == "class_def":
            # 提取类名
            class_name = None
            for cid in children.get(nid, []):
                child = nodes[cid]
                if child.kind == "identifier":
                    class_name = child.text.strip()
                    break

            if class_name:
                # 在类中查找构造函数（需要递归搜索，因为函数可能在block节点内）
                def find_constructor_in_class(class_node_id: int) -> Optional[int]:
                    def search_in_node(node_id: int) -> Optional[int]:
                        for cid in children.get(node_id, []):
                            child = nodes[cid]
                            if child.kind == "function_def":
                                # 检查是否是构造函数
                                for func_cid in children.get(cid, []):
                                    func_child = nodes[func_cid]
                                    if func_child.kind == "identifier":
                                        func_name = func_child.text.strip()
                                        if func_name in ("__init__", "constructor"):
                                            return cid
                                        break
                            elif child.kind in ("block", "class_body", "declaration_list"):
                                # 递归搜索block节点
                                result = search_in_node(cid)
                                if result:
                                    return result
                        return None

                    return search_in_node(class_node_id)

                init_id = find_constructor_in_class(nid)
                if init_id:
                    class_name_to_init[class_name] = init_id

    # 2) 构建函数名映射
    func_name_to_id: Dict[str, int] = {}

    def extract_function_name(func_id: int) -> Optional[str]:
        """
        提取函数名，支持不同语言的AST结构：
        - Python: identifier是直接子节点
        - JavaScript: property_identifier是直接子节点（现在映射为identifier）
        - C: 函数签名在'other'节点中
        - Java: identifier是直接子节点（跳过修饰符和类型）

        策略顺序（优化后）：
        1. 优先检查'other'节点是否包含函数签名（C/JavaScript）
        2. 在declarator节点中查找identifier（C的另一种形式）
        3. 收集直接identifier子节点，取最后一个（Python/Java）
        """
        # 策略1：优先检查'other'节点（C/JavaScript）
        # 对于C函数，'other'节点包含完整签名如 "createPoint(int x, int y)"
        # 需要排除Python的类型标注
        python_type_keywords = {
            'str', 'int', 'bool', 'float', 'dict', 'list', 'tuple', 'set',
            'bytes', 'bytearray', 'complex', 'frozenset', 'None', 'Any',
            'Optional', 'Union', 'Callable', 'Iterable', 'Iterator',
            'Sequence', 'Mapping', 'Type', 'TypeVar', 'Generic'
        }

        for cid in children.get(func_id, []):
            child = nodes[cid]
            if child.kind == 'other':
                func_name = child.text.strip()
                # 跳过Python类型标注
                # 1. 包含括号的（如 List[str], Dict[str, int]）
                if '[' in func_name or ']' in func_name:
                    continue
                # 2. 常见类型关键字（如 str, int, bool）
                if func_name in python_type_keywords:
                    continue
                # 检查是否包含函数签名（带括号）
                if '(' in func_name:
                    func_name = func_name.split('(')[0].strip()
                # 排除修饰符关键字
                if func_name and func_name not in {'static', 'public', 'private', 'protected', 'public static', 'private static'}:
                    return func_name

        # 策略2：在declarator相关节点中查找（C的另一种形式）
        declarator_kinds = {'declarator', 'function_declarator'}
        for cid in children.get(func_id, []):
            child = nodes[cid]
            if child.kind in declarator_kinds:
                # 在declarator节点的子节点中查找identifier
                for cid2 in children.get(cid, []):
                    child2 = nodes[cid2]
                    if child2.kind == "identifier":
                        return child2.text.strip()

        # 策略3：收集所有直接的identifier子节点（Python/Java）
        direct_identifiers = []
        for cid in children.get(func_id, []):
            child = nodes[cid]
            if child.kind == "identifier":
                direct_identifiers.append(child.text.strip())

        # 如果有直接identifier，取最后一个
        if len(direct_identifiers) > 0:
            # 取最后一个identifier作为函数名
            # Java: 前面可能有类型标识符，最后一个是方法名
            # Python: 只有一个identifier就是函数名
            return direct_identifiers[-1]

        return None

    # 收集所有函数定义并构建CFG
    for nid, node in nodes.items():
        if node.kind == "function_def":
            func_cfg = build_function_cfg(nid, index)
            cfg.functions[nid] = func_cfg

            # 提取函数名
            func_name = extract_function_name(nid)
            if func_name:
                func_name_to_id[func_name] = nid

    # 3) 构建模块级CFG
    module_stmts = _find_module_level_statements(index)
    if module_stmts:
        module_cfg = FunctionCFG(
            func_id=-1,
            entry=module_stmts[0] if module_stmts else None,
            exits=set([module_stmts[-1]]) if module_stmts else set(),
        )
        module_cfg.nodes_all = nodes

        for i in range(len(module_stmts)):
            module_cfg.nodes[module_stmts[i]] = nodes[module_stmts[i]]
            if i > 0:
                _connect(module_cfg, module_stmts[i-1], module_stmts[i])

        del module_cfg.nodes_all
        cfg.module_cfg = module_cfg
        cfg.entry_points.append(-1)  # 模块级是入口点

    # 如果没有模块级代码，尝试找main函数作为入口
    if not cfg.module_cfg:
        main_id = func_name_to_id.get("main")
        if main_id:
            cfg.entry_points.append(main_id)

    # 4) 增强的调用识别：遍历所有CFG节点，识别所有调用
    all_contexts: List[Tuple[int, Dict[int, Any]]] = [(fid, fcfg.nodes) for fid, fcfg in cfg.functions.items()]
    if cfg.module_cfg:
        all_contexts.append((-1, cfg.module_cfg.nodes))

    # 使用集合跟踪已处理的调用，避免重复
    seen_calls: Set[Tuple[int, int]] = set()  # (context_id, call_id)

    for context_id, context_nodes in all_contexts:
        for stmt_id in context_nodes:
            # 在这个语句中查找所有调用
            calls = _find_all_calls_in_node(stmt_id, index)

            for call_id, stmt_id in calls:
                # 检查是否已经处理过这个调用
                call_key = (context_id, call_id)
                if call_key in seen_calls:
                    continue
                seen_calls.add(call_key)

                func_name, _ = _extract_call_info(call_id, index)

                if not func_name:
                    continue

                # 尝试解析目标函数
                callee_id = None

                # 1. 直接函数调用
                if func_name in func_name_to_id:
                    callee_id = func_name_to_id[func_name]

                # 2. 类构造函数调用（Python: Point(...) -> __init__）
                elif func_name in class_name_to_init:
                    callee_id = class_name_to_init[func_name]

                # 创建CallSite对象
                call_site = CallSite(
                    call_node_id=call_id,
                    caller_context_id=context_id,
                    callee_name=func_name,
                    callee_id=callee_id,
                    statement_id=stmt_id,
                )
                cfg.call_sites.append(call_site)

                # 保留向后兼容的call_edges
                if callee_id is not None:
                    cfg.call_edges.append((context_id, callee_id, call_id))

    return cfg