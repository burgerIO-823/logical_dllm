from __future__ import annotations

from code_extractor.bootstrap.languages import make_registry
from code_extractor.parsers.parser import TreeSitterCodeParser, ParsedCode
from code_extractor.parsers.ast import AstExtractor
from code_extractor.graphs.ast_index import build_ast_index
from code_extractor.graphs.def_use import build_def_use

SAMPLES = {
    "python": """\
def add(a, b):
    c = a + b
    if c > 0:
        d = c + 1
    return d
""",
    "javascript": """\
function add(a, b) {
  let c = a + b;
  if (c > 0) {
    let d = c + 1;
    return d;
  }
}
""",
    "c": """\
int add(int a, int b) {
  int c = a + b;
  if (c > 0) {
    int d = c + 1;
    return d;
  }
}
""",
    "java": """\
class T {
  int add(int a, int b) {
    int c = a + b;
    if (c > 0) {
      int d = c + 1;
      return d;
    }
  }
}
""",
}


def run_once(lang_name: str, code: str):
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

    # 简单打印
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


def main():
    for lang in ["python", "javascript", "c", "java"]:
        code = SAMPLES.get(lang)
        if not code:
            print(f"\n=== [{lang}] sample missing, skip ===")
            continue
        try:
            run_once(lang, code)
        except Exception as e:
            print(f"  ✗ Error for {lang}: {e}")


if __name__ == "__main__":
    main()