from __future__ import annotations

from code_extractor.bootstrap.languages import make_registry
from code_extractor.parsers.parser import TreeSitterCodeParser, ParsedCode
from code_extractor.parsers.ast import AstExtractor
from code_extractor.graphs.ast_index import build_ast_index
from code_extractor.graphs.def_use import build_def_use
from code_extractor.graphs.visualizer import visualize_def_use, GRAPHVIZ_AVAILABLE

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

def run_once(lang_name: str, code: str, output_dir: str = "./defuse_visualizations"):
    print(f"\n=== [Def-Use {lang_name}] ===")
    reg = make_registry()
    wrapper = reg.get_wrapper(lang_name)

    parser = TreeSitterCodeParser({lang_name: wrapper})
    parsed: ParsedCode = parser.parse(code, lang_name)

    extractor = AstExtractor(keep_unnamed=False, text_limit=200)
    nodes, edges_ast = extractor.extract(parsed, wrapper)

    # 1) 规范化 AST 输入
    index = build_ast_index(nodes, edges_ast)

    # 2) 构建 def-use 图
    dug = build_def_use(index)

    # 3) 打印文本结果
    print("Defs:")
    for nid, names in sorted(dug.defs.items()):
        n = index.nodes_by_id[nid]
        print(f"  id={nid:3d} kind={n.kind:12s} type={n.type:20s} -> {sorted(names)}")

    print("Uses:")
    for nid, names in sorted(dug.uses.items()):
        n = index.nodes_by_id[nid]
        print(f"  id={nid:3d} kind={n.kind:12s} type={n.type:20s} -> {sorted(names)}")

    print("Def-Use edges:")
    for def_id, use_id, v in dug.edges:
        dn = index.nodes_by_id[def_id]
        un = index.nodes_by_id[use_id]
        print(
            f"  {v}: def(id={def_id}, kind={dn.kind}, span={dn.span})"
            f"  -> use(id={use_id}, kind={un.kind}, span={un.span})"
        )

    # 4) 生成可视化图形
    print(f"\n--- Generating visualization for {lang_name} ---")
    if GRAPHVIZ_AVAILABLE:
        output_path = f"{output_dir}/defuse_{lang_name}"
        result = visualize_def_use(
            dug=dug,
            index=index,
            output_path=output_path,
            format="png",
            view=False,
            max_edges=None,  # 显示所有边
            show_isolated_nodes=False,  # 不显示孤立节点
        )
        if result:
            print(f"✓ Def-Use visualization saved: {result}")
    else:
        print("⚠ Graphviz not available. Install with: pip install graphviz")
        print("  Skipping graphical visualization (text output shown above)")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test Def-Use graph construction and visualization")
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
        default="./defuse_visualizations",
        help="Output directory for visualizations",
    )

    args = parser.parse_args()

    # 确定要处理的语言
    if args.lang == "all":
        languages = ["python", "javascript", "c", "java"]
    else:
        languages = [args.lang]

    print("=" * 80)
    print("Def-Use Graph Construction and Visualization Test")
    print("=" * 80)
    if not GRAPHVIZ_AVAILABLE:
        print("⚠ Note: Graphviz not installed - only text output will be shown")
        print("  Install with: pip install graphviz")
        print("=" * 80)

    for lang in languages:
        code = SAMPLES.get(lang)
        if not code:
            print(f"\n=== [{lang}] sample missing, skip ===")
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