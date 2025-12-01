"""
Test LogicGraph - Multi-language support

Tests the LogicGraph construction and visualization for:
- Python (module-level code)
- JavaScript (module-level code)
- C (main function)
- Java (main method)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from code_extractor.bootstrap.languages import make_registry
from code_extractor.parsers.parser import TreeSitterCodeParser
from code_extractor.parsers.ast import AstExtractor
from code_extractor.graphs.ast_index import build_ast_index
from code_extractor.graphs.cfg import build_cfg
from code_extractor.graphs.def_use import build_def_use
from code_extractor.graphs.logic_graph import build_logic_graph
from code_extractor.graphs.visualizer import visualize_cfg


# Test code samples for each language
TEST_CASES = {
    "python": """
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def shift(self, dx, dy):
        return Point(self.x + dx, self.y + dy)

def add(a, b):
    return a + b

p = Point(1, 2)
q = p.shift(3, 4)
r = add(5, 6)
""",
    "javascript": """
class Point {
    constructor(x, y) {
        this.x = x;
        this.y = y;
    }

    shift(dx, dy) {
        return new Point(this.x + dx, this.y + dy);
    }
}

function add(a, b) {
    return a + b;
}

const p = new Point(1, 2);
const q = p.shift(3, 4);
const r = add(5, 6);
""",
    "c": """
typedef struct {
    int x;
    int y;
} Point;

Point createPoint(int x, int y) {
    Point p = {x, y};
    return p;
}

Point shift(Point p, int dx, int dy) {
    Point result = {p.x + dx, p.y + dy};
    return result;
}

int add(int a, int b) {
    return a + b;
}

int main() {
    Point p = createPoint(1, 2);
    Point q = shift(p, 3, 4);
    int r = add(5, 6);
    return 0;
}
""",
    "java": """
class Point {
    int x, y;

    Point(int x, int y) {
        this.x = x;
        this.y = y;
    }

    Point shift(int dx, int dy) {
        return new Point(this.x + dx, this.y + dy);
    }
}

class Main {
    static int add(int a, int b) {
        return a + b;
    }

    public static void main(String[] args) {
        Point p = new Point(1, 2);
        Point q = p.shift(3, 4);
        int r = add(5, 6);
    }
}
"""
}


def test_language(lang_name: str, code: str, verbose: bool = False):
    """Test LogicGraph for a specific language."""
    print(f"\n{'='*80}")
    print(f"Testing: {lang_name.upper()}")
    print(f"{'='*80}")

    try:
        # Parse code
        reg = make_registry()
        wrapper = reg.get_wrapper(lang_name)
        parser = TreeSitterCodeParser({lang_name: wrapper})
        parsed = parser.parse(code, lang_name)

        # Extract AST
        extractor = AstExtractor(keep_unnamed=False, text_limit=120)
        nodes, edges = extractor.extract(parsed, wrapper)
        index = build_ast_index(nodes, edges)

        # Build CFG and Def-Use
        cfg = build_cfg(index)
        dug = build_def_use(index)

        # Build LogicGraph
        logic_graph = build_logic_graph(cfg, dug, index)

        # Print statistics
        print(f"\n✓ LogicGraph successfully built")
        print(f"  Entry Point: {logic_graph.entry_point}")
        print(f"  Statement Nodes: {len(logic_graph.statement_nodes)}")
        print(f"  Data Dependency Edges: {len(logic_graph.data_edges)}")
        print(f"  Function Call Edges: {len(logic_graph.call_edges)}")
        print(f"  Function Definitions: {len(logic_graph.function_defs)}")

        if verbose:
            print(f"\nStatements:")
            for node_id in sorted(logic_graph.statement_nodes):
                node = index.nodes_by_id.get(node_id)
                print(f"  • {node.text.strip()}")

            print(f"\nData Dependencies:")
            for edge in logic_graph.data_edges:
                src_node = index.nodes_by_id.get(edge.source_id)
                dst_node = index.nodes_by_id.get(edge.target_id)
                symbols = ', '.join(sorted(edge.shared_symbols))
                print(f"  • {src_node.text.strip()}")
                print(f"    └─> {dst_node.text.strip()} (via: {symbols})")

            print(f"\nFunction Calls:")
            for call in logic_graph.call_edges:
                stmt_node = index.nodes_by_id.get(call.statement_id)
                print(f"  • {stmt_node.text.strip()} -> {call.callee_name}")

        # Generate visualization
        viz_output = project_root / "cfg_visualizations" / f"cfg_{lang_name}_logic"
        result = visualize_cfg(cfg, index, str(viz_output), view_mode="simple")
        print(f"\n✓ Visualization saved to: {result}")

        return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run tests for all languages."""
    import argparse

    parser = argparse.ArgumentParser(description="Test LogicGraph for multiple languages")
    parser.add_argument(
        "--lang",
        choices=list(TEST_CASES.keys()) + ["all"],
        default="all",
        help="Language to test (default: all)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed information",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("LogicGraph Multi-Language Test")
    print("=" * 80)

    # Select languages to test
    if args.lang == "all":
        languages = TEST_CASES.keys()
    else:
        languages = [args.lang]

    # Run tests
    results = {}
    for lang_name in languages:
        code = TEST_CASES[lang_name]
        success = test_language(lang_name, code, verbose=args.verbose)
        results[lang_name] = success

    # Summary
    print(f"\n{'='*80}")
    print("Summary")
    print(f"{'='*80}")
    for lang_name, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {lang_name}")

    print(f"{'='*80}")

    # Exit code
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
