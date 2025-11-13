# code_extractor/tests/smoke_ast.py
from __future__ import annotations
from pathlib import Path

# 统一从包内绝对导入
from code_extractor.bootstrap.languages import make_registry
from code_extractor.parsers.parser import TreeSitterCodeParser
from code_extractor.parsers.ast import AstExtractor

SAMPLES = {
    "python": """\
def add(a, b):
    if a > 0:
        return a + b
    else:
        return b - a
""",
    "javascript": """\
function add(a, b) {
  if (a > 0) { return a + b; }
  else { return b - a; }
}
""",
    "c": """\
int add(int a, int b) {
  if (a > 0) return a + b;
  else return b - a;
}
""",
    "java": """\
class T {
  int add(int a, int b) {
    if (a > 0) return a + b;
    else return b - a;
  }
}
""",
}

def debug_print_tree(nodes, edges, max_depth=5, indent=2, max_children=6):
    """把 AST 结构按树形打印（只做预览，不是完整 dump）"""
    id2node = {n.id: n for n in nodes}
    children = {}
    roots = set(id2node.keys())
    for p, c in edges:
        children.setdefault(p, []).append(c)
        if c in roots:
            roots.remove(c)
    # 一般只有一个根；若有多个，就都遍历一下
    root_ids = list(roots) if roots else [0]

    def dfs(nid, depth=0):
        if depth > max_depth:
            return
        node = id2node[nid]
        prefix = " " * (indent * depth)
        preview = node.text.replace("\n", " ")[:60]
        print(f"{prefix}- [{node.kind}] ({node.type}) span={node.span} text='{preview}'")
        for i, cid in enumerate(children.get(nid, [])[:max_children]):
            dfs(cid, depth + 1)
        if len(children.get(nid, [])) > max_children:
            print(prefix + "  ...")

    for rid in root_ids:
        dfs(rid)

def run_once(lang_name: str, code: str):
    print(f"\n=== [{lang_name}] ===")
    reg = make_registry()
    wrapper = reg.get_wrapper(lang_name)

    parser = TreeSitterCodeParser({lang_name: wrapper})
    parsed = parser.parse(code, lang_name)

    extractor = AstExtractor(keep_unnamed=False, text_limit=120)
    nodes, edges = extractor.extract(parsed, wrapper)

    print(f"Nodes: {len(nodes)}, Edges(AST): {len(edges)}")
    if nodes:
        print("Root preview:")
        debug_print_tree(nodes, edges, max_depth=5)
    else:
        print("No nodes extracted.")

def main():
    # 你可以把下面的列表改成想测的语言子集
    for lang in ["python", "javascript", "c", "java"]:
        code = SAMPLES.get(lang)
        if code is None:
            print(f"\n=== [{lang}] sample missing, skip ===")
            continue
        try:
            run_once(lang, code)
        except Exception as e:
            print(f"  ✗ Error for {lang}: {e}")

if __name__ == "__main__":
    main()
