# code_extractor/test_scripts/test_cfg.py
from __future__ import annotations

from code_extractor.bootstrap.languages import make_registry
from code_extractor.parsers.parser import TreeSitterCodeParser
from code_extractor.parsers.ast import AstExtractor
from code_extractor.graphs.ast_index import AstIndex, build_ast_index
from code_extractor.graphs.cfg import build_cfg  # 你之前实现的 CFG 构建入口
from code_extractor.graphs.cfg import ControlFlowGraph  # 如果有导出的话，可选
from code_extractor.graphs.visualizer import visualize_cfg, GRAPHVIZ_AVAILABLE


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


def debug_print_cfg(cfg: ControlFlowGraph, index: AstIndex, max_edges_per_func: int = 20):
    """
    根据现在的 ControlFlowGraph 结构（functions -> FunctionCFG）打印 CFG 信息
    增强：也打印模块级CFG和调用边
    """
    # Print module-level CFG if exists
    if cfg.module_cfg:
        print(f"\nModule Level CFG:")
        print(f"  entry: {cfg.module_cfg.entry}, exits: {sorted(cfg.module_cfg.exits) if cfg.module_cfg.exits else []}")
        print(f"  Module nodes: {len(cfg.module_cfg.nodes)}")
        module_edges = []
        for src, dsts in cfg.module_cfg.succ.items():
            for dst in dsts:
                module_edges.append((src, dst))
        print(f"  Module edges: {len(module_edges)}")
        if module_edges:
            print("  Some module edges:")
            for (src, dst) in module_edges[:max_edges_per_func]:
                src_node = index.nodes_by_id.get(src)
                preview = src_node.text.replace("\n", " ")[:40] if src_node else "<?>"
                print(f"    {src:3d} -> {dst:3d} :: {preview}")

    # Print function call edges
    if cfg.call_edges:
        print(f"\nFunction Call Relationships: {len(cfg.call_edges)} calls")
        for caller_id, callee_id, _ in cfg.call_edges:
            caller_name = "Module" if caller_id == -1 else f"Func{caller_id}"
            callee_node = index.nodes_by_id.get(callee_id)
            callee_name = callee_node.text.strip()[:30] if callee_node else f"Func{callee_id}"
            print(f"  {caller_name} -> {callee_name}")

    if not cfg.functions:
        if not cfg.module_cfg:
            print("CFG is empty (no functions or module code found).")
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


def run_once(lang: str, code: str, output_dir: str = "./cfg_visualizations"):
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

    # 4) 打印文本结果
    debug_print_cfg(cfg, index)

    # 5) 生成可视化图形
    print(f"\n--- Generating visualization for {lang} ---")
    if GRAPHVIZ_AVAILABLE:
        output_path = f"{output_dir}/cfg_{lang}"
        result = visualize_cfg(
            cfg=cfg,
            index=index,
            output_path=output_path,
            format="png",
            view=False,
        )
        if result:
            print(f"✓ CFG visualization saved: {result}")
    else:
        print("⚠ Graphviz not available. Install with: pip install graphviz")
        print("  Skipping graphical visualization (text output shown above)")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test CFG construction and visualization")
    parser.add_argument(
        "--lang",
        type=str,
        choices=list(SAMPLES.keys()) + ["all"],
        default="all",
        help="Language to test (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./cfg_visualizations",
        help="Output directory for visualizations",
    )

    args = parser.parse_args()

    # 确定要处理的语言
    if args.lang == "all":
        languages = ["python", "javascript", "c", "java"]
    else:
        languages = [args.lang]

    print("=" * 80)
    print("CFG Construction and Visualization Test")
    print("=" * 80)
    if not GRAPHVIZ_AVAILABLE:
        print("⚠ Note: Graphviz not installed - only text output will be shown")
        print("  Install with: pip install graphviz")
        print("=" * 80)

    for lang in languages:
        code = SAMPLES.get(lang)
        if code is None:
            print(f"\n=== [CFG {lang}] sample missing, skip ===")
            continue
        try:
            run_once(lang, code, output_dir=args.output_dir)
        except Exception as e:
            print(f"  ✗ Error for {lang}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)
    print("All tests complete!")
    if GRAPHVIZ_AVAILABLE:
        print(f"Visualizations saved in: {args.output_dir}/")
    print("=" * 80)


if __name__ == "__main__":
    main()