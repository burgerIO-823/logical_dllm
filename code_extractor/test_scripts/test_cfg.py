# code_extractor/test_scripts/test_cfg.py
from __future__ import annotations

from typing import Dict, List
from code_extractor.bootstrap.languages import make_registry
from code_extractor.parsers.parser import TreeSitterCodeParser
from code_extractor.parsers.ast import AstExtractor
from code_extractor.graphs.ast_index import AstIndex
from code_extractor.graphs.cfg import build_cfg  # 你之前实现的 CFG 构建入口
from code_extractor.graphs.cfg import ControlFlowGraph, FunctionCFG  # 如果有导出的话，可选


# 和 test_ast.py 保持一致的 samples
SAMPLES = {
    "python": """\
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def shift(self, dx, dy):
        nx = self.x + dx
        ny = self.y + dy
        return Point(nx, ny)

def add(a, b):
    c = a + b
    if c > 0:
        d = c + 1
    return d

p = Point(1, 2)
q = p.shift(3, 4)
""",

    "javascript": """\
class Point {
  constructor(x, y) {
    this.x = x;
    this.y = y;
  }

  shift(dx, dy) {
    const nx = this.x + dx;
    const ny = this.y + dy;
    return new Point(nx, ny);
  }
}

function add(a, b) {
  let c = a + b;
  if (c > 0) {
    let d = c + 1;
    return d;
  }
}

const p = new Point(1, 2);
const q = p.shift(3, 4);
""",

    "c": """\
typedef struct Point {
  int x;
  int y;
} Point;

Point shift(Point p, int dx, int dy) {
  Point res;
  res.x = p.x + dx;
  res.y = p.y + dy;
  return res;
}

int add(int a, int b) {
  int c = a + b;
  if (c > 0) {
    int d = c + 1;
    return d;
  }
  return c;
}

int main() {
  Point p;
  p.x = 1;
  p.y = 2;
  Point q = shift(p, 3, 4);
  int r = add(q.x, q.y);
  return r;
}
""",

    "java": """\
class Point {
  int x, y;

  Point(int x, int y) {
    this.x = x;
    this.y = y;
  }

  Point shift(int dx, int dy) {
    int nx = this.x + dx;
    int ny = this.y + dy;
    return new Point(nx, ny);
  }
}

class T {
  int add(int a, int b) {
    int c = a + b;
    if (c > 0) {
      int d = c + 1;
      return d;
    }
    return c;
  }

  void run() {
    Point p = new Point(1, 2);
    Point q = p.shift(3, 4);
    int r = add(q.x, q.y);
  }
}
""",
}


def build_ast_index(nodes, edges) -> AstIndex:
    """
    从 AstExtractor.extract() 的输出构造 AstIndex：
      - nodes_by_id
      - children
      - parent
      - preorder（前序遍历顺序）
    """
    # id -> node
    nodes_by_id = {n.id: n for n in nodes}

    # parent / children
    children: Dict[int, List[int]] = {}
    parent: Dict[int, int] = {}
    for p, c in edges:
        children.setdefault(p, []).append(c)
        parent[c] = p

    # 找根节点：那些不在 parent 字典里的 id
    all_ids = set(nodes_by_id.keys())
    root_ids = [nid for nid in all_ids if nid not in parent]

    # 前序遍历
    preorder: List[int] = []

    def dfs(nid: int):
        preorder.append(nid)
        for cid in children.get(nid, []):
            dfs(cid)

    for rid in root_ids:
        dfs(rid)

    # 构造 AstIndex（注意这里填全 4 个参数）
    return AstIndex(nodes_by_id, children, parent, preorder)


def debug_print_cfg(cfg: ControlFlowGraph, index: AstIndex, max_edges_per_func: int = 20):
    """
    根据现在的 ControlFlowGraph 结构（functions -> FunctionCFG）打印 CFG 信息
    """
    if not cfg.functions:
        print("CFG is empty (no functions found).")
        return

    for func_id, fcfg in cfg.functions.items():
        func_node = index.nodes_by_id.get(func_id)
        func_name = (func_node.text.strip() if func_node else f"<id {func_id}>")[:30]

        print(f"\nFunction CFG for node {func_id}: '{func_name}'")
        print(f"  entry: {fcfg.entry}, exits: {sorted(fcfg.exits) if fcfg.exits else []}")
        print(f"  CFG nodes: {len(fcfg.nodes)}")

        # 将 succ 邻接表展平为边列表
        edges = []
        for src, dsts in fcfg.succ.items():
            for dst in dsts:
                edges.append((src, dst))

        print(f"  CFG edges: {len(edges)}")
        print("  Some edges (src -> dst :: src_text_preview):")

        for (src, dst) in edges[:max_edges_per_func]:
            src_node = index.nodes_by_id.get(src)
            preview = src_node.text.replace("\n", " ")[:40] if src_node else "<?>"
            print(f"    {src:3d} -> {dst:3d} :: {preview}")

        if len(edges) > max_edges_per_func:
            print("    ...")


def run_once(lang: str, code: str):
    print(f"\n=== [CFG {lang}] ===")

    # 1) registry + parser + AST
    reg = make_registry()
    wrapper = reg.get_wrapper(lang)
    parser = TreeSitterCodeParser({lang: wrapper})
    parsed = parser.parse(code, lang)

    extractor = AstExtractor(keep_unnamed=False, text_limit=120)
    nodes, edges = extractor.extract(parsed, wrapper)

    print(f"AST nodes: {len(nodes)}, AST edges: {len(edges)}")

    if not nodes:
        print("  (no AST nodes, skip)")
        return

    # 2) 构造 AstIndex（修正点：补全 parent / preorder）
    index = build_ast_index(nodes, edges)

    # 3) 构建 CFG
    cfg = build_cfg(index)

    # 4) 打印一点结果
    debug_print_cfg(cfg, index)


def main():
    for lang in ["python", "javascript", "c", "java"]:
        code = SAMPLES.get(lang)
        if code is None:
            print(f"\n=== [CFG {lang}] sample missing, skip ===")
            continue
        try:
            run_once(lang, code)
        except Exception as e:
            print(f"  ✗ Error for {lang}: {e}")


if __name__ == "__main__":
    main()