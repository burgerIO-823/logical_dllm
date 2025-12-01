"""
Benchmark Testing Script for Logic Graph Construction

Tests the logic graph construction pipeline on real benchmark problems:
- HumanEval
- HumanEval++
- APPS-Medium

For each problem, this script:
1. Parses the code using TreeSitter
2. Extracts AST and builds AST index
3. Constructs Control Flow Graph (CFG)
4. Builds Def-Use Graph (DUG)
5. Creates Logic Graph combining CFG and DUG
6. Generates visualizations
7. Collects and reports statistics
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from code_extractor.bootstrap.languages import make_registry
from code_extractor.parsers.parser import TreeSitterCodeParser
from code_extractor.parsers.ast import AstExtractor
from code_extractor.graphs.ast_index import build_ast_index
from code_extractor.graphs.cfg import build_cfg
from code_extractor.graphs.def_use import build_def_use
from code_extractor.graphs.logic_graph import build_logic_graph
from code_extractor.graphs.visualizer import visualize_cfg


class BenchmarkTest:
    """Represents a single benchmark test case."""

    def __init__(self, name: str, category: str, file_path: Path):
        self.name = name
        self.category = category
        self.file_path = file_path
        self.code = file_path.read_text()
        self.language = "python"
        self.results: Dict[str, Any] = {}

    def __repr__(self):
        return f"BenchmarkTest({self.category}/{self.name})"


def run_test(test: BenchmarkTest, output_dir: Path, verbose: bool = False) -> Dict[str, Any]:
    """
    Run a single benchmark test through the full pipeline.

    Returns a dictionary with statistics and results.
    """
    results = {
        "name": test.name,
        "category": test.category,
        "language": test.language,
        "status": "pending",
        "error": None,
        "timings": {},
        "stats": {},
    }

    try:
        # Step 1: Parse code
        start = time.time()
        reg = make_registry()
        wrapper = reg.get_wrapper(test.language)
        parser = TreeSitterCodeParser({test.language: wrapper})
        parsed = parser.parse(test.code, test.language)
        results["timings"]["parse"] = time.time() - start

        # Step 2: Extract AST
        start = time.time()
        extractor = AstExtractor(keep_unnamed=False, text_limit=120)
        nodes, edges = extractor.extract(parsed, wrapper)
        index = build_ast_index(nodes, edges)
        results["timings"]["ast_extract"] = time.time() - start
        results["stats"]["ast_nodes"] = len(nodes)
        results["stats"]["ast_edges"] = len(edges)

        # Step 3: Build CFG
        start = time.time()
        cfg = build_cfg(index)
        results["timings"]["cfg_build"] = time.time() - start
        results["stats"]["cfg_functions"] = len(cfg.functions)
        results["stats"]["cfg_call_sites"] = len(cfg.call_sites)

        # Step 4: Build Def-Use Graph
        start = time.time()
        dug = build_def_use(index)
        results["timings"]["dug_build"] = time.time() - start
        results["stats"]["dug_defs"] = len(dug.defs)
        results["stats"]["dug_uses"] = len(dug.uses)

        # Step 5: Build Logic Graph
        start = time.time()
        logic_graph = build_logic_graph(cfg, dug, index)
        results["timings"]["logic_graph_build"] = time.time() - start
        results["stats"]["logic_statements"] = len(logic_graph.statement_nodes)
        results["stats"]["logic_data_edges"] = len(logic_graph.data_edges)
        results["stats"]["logic_call_edges"] = len(logic_graph.call_edges)
        results["stats"]["logic_function_call_edges"] = len(logic_graph.function_call_edges)
        results["stats"]["logic_functions"] = len(logic_graph.function_defs)
        results["stats"]["logic_entry_point"] = logic_graph.entry_point

        # Step 6: Generate visualization
        start = time.time()
        viz_filename = f"{test.category}_{test.name}"
        viz_path = output_dir / viz_filename
        visualize_cfg(cfg, index, str(viz_path), format="png", view_mode="simple")
        results["timings"]["visualization"] = time.time() - start
        results["visualization_path"] = str(viz_path) + ".png"

        results["status"] = "success"
        results["total_time"] = sum(results["timings"].values())

        if verbose:
            print(f"\n{'='*80}")
            print(f"✓ {test.category}/{test.name}")
            print(f"{'='*80}")
            print(f"AST: {results['stats']['ast_nodes']} nodes, {results['stats']['ast_edges']} edges")
            print(f"CFG: {results['stats']['cfg_functions']} functions, {results['stats']['cfg_call_sites']} call sites")
            print(f"DUG: {results['stats']['dug_defs']} defs, {results['stats']['dug_uses']} uses")
            print(f"Logic Graph:")
            print(f"  - Statements: {results['stats']['logic_statements']}")
            print(f"  - Data edges: {results['stats']['logic_data_edges']}")
            print(f"  - Module→Function call edges: {results['stats']['logic_call_edges']}")
            print(f"  - Function→Function call edges: {results['stats']['logic_function_call_edges']}")
            print(f"  - Functions: {results['stats']['logic_functions']}")
            print(f"  - Entry point: {results['stats']['logic_entry_point']}")
            print(f"Total time: {results['total_time']:.3f}s")
            print(f"Visualization: {results['visualization_path']}")

    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        if verbose:
            print(f"\n{'='*80}")
            print(f"✗ {test.category}/{test.name}")
            print(f"{'='*80}")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

    return results


def main():
    """Run all benchmark tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Test logic graph on benchmark problems")
    parser.add_argument(
        "--category",
        choices=["humaneval", "humaneval_plus", "apps_medium", "all"],
        default="all",
        help="Which benchmark category to test (default: all)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed information",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Only print summary, skip per-test details",
    )

    args = parser.parse_args()

    # Setup paths
    script_dir = Path(__file__).parent
    shorteval_dir = script_dir.parent
    problems_dir = shorteval_dir / "problems"
    results_dir = shorteval_dir / "results"
    results_dir.mkdir(exist_ok=True)

    # Collect test cases
    test_cases: List[BenchmarkTest] = []

    categories = ["humaneval", "humaneval_plus", "apps_medium"] if args.category == "all" else [args.category]

    for category in categories:
        category_dir = problems_dir / category
        if category_dir.exists():
            for py_file in category_dir.glob("*.py"):
                test_name = py_file.stem
                test_cases.append(BenchmarkTest(test_name, category, py_file))

    if not test_cases:
        print("No test cases found!")
        return 1

    # Run tests
    print("="*80)
    print(f"Benchmark Testing - Logic Graph Construction")
    print("="*80)
    print(f"Found {len(test_cases)} test case(s)")
    print(f"Categories: {', '.join(categories)}")
    print("="*80)

    all_results = []
    for test in test_cases:
        if not args.summary_only:
            print(f"\nProcessing: {test.category}/{test.name}...")
        result = run_test(test, results_dir, verbose=args.verbose and not args.summary_only)
        all_results.append(result)
        if not args.verbose and not args.summary_only:
            status_symbol = "✓" if result["status"] == "success" else "✗"
            print(f"  {status_symbol} {result['status']}: {result.get('total_time', 0):.3f}s")

    # Print summary
    print(f"\n{'='*80}")
    print("Summary")
    print(f"{'='*80}")

    successful = [r for r in all_results if r["status"] == "success"]
    failed = [r for r in all_results if r["status"] == "failed"]

    print(f"\nResults: {len(successful)}/{len(all_results)} successful")

    if successful:
        print("\n✓ Successful Tests:")
        for result in successful:
            print(f"  • {result['category']}/{result['name']}")
            print(f"    - Statements: {result['stats']['logic_statements']}, "
                  f"Data edges: {result['stats']['logic_data_edges']}")
            print(f"    - Module→Func calls: {result['stats']['logic_call_edges']}, "
                  f"Func→Func calls: {result['stats']['logic_function_call_edges']}")
            print(f"    - Time: {result['total_time']:.3f}s")

    if failed:
        print("\n✗ Failed Tests:")
        for result in failed:
            print(f"  • {result['category']}/{result['name']}: {result['error']}")

    # Statistics
    if successful:
        print(f"\n{'='*80}")
        print("Aggregate Statistics")
        print(f"{'='*80}")

        avg_time = sum(r["total_time"] for r in successful) / len(successful)
        avg_statements = sum(r["stats"]["logic_statements"] for r in successful) / len(successful)
        avg_data_edges = sum(r["stats"]["logic_data_edges"] for r in successful) / len(successful)
        avg_call_edges = sum(r["stats"]["logic_call_edges"] for r in successful) / len(successful)
        avg_functions = sum(r["stats"]["logic_functions"] for r in successful) / len(successful)

        print(f"Average processing time: {avg_time:.3f}s")
        print(f"Average statements per problem: {avg_statements:.1f}")
        print(f"Average data edges per problem: {avg_data_edges:.1f}")
        print(f"Average call edges per problem: {avg_call_edges:.1f}")
        print(f"Average functions per problem: {avg_functions:.1f}")

    print(f"\n{'='*80}")
    print(f"All visualizations saved to: {results_dir}")
    print(f"{'='*80}")

    return 0 if len(failed) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
