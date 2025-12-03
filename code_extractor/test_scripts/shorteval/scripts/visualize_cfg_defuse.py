"""
Visualize CFG and Def-Use graphs for benchmark test problems.

This script generates CFG and def-use visualizations for the three selected
benchmark problems from HumanEval, HumanEval++, and APPS-Medium.
"""

import sys
from pathlib import Path

# Add parent directories to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from code_extractor.bootstrap.languages import make_registry
from code_extractor.parsers.parser import TreeSitterCodeParser
from code_extractor.parsers.ast import AstExtractor
from code_extractor.graphs.ast_index import build_ast_index
from code_extractor.graphs.cfg import build_cfg
from code_extractor.graphs.def_use import build_def_use
from code_extractor.graphs.visualizer import visualize_cfg, visualize_def_use


def visualize_problem(problem_path: str, problem_name: str, output_dir: Path):
    """
    Visualize CFG and def-use graphs for a given problem.

    Args:
        problem_path: Path to the problem source file
        problem_name: Name for output files
        output_dir: Directory to save visualizations
    """
    print(f"\n{'='*60}")
    print(f"Processing: {problem_name}")
    print(f"{'='*60}")

    # Load source code
    with open(problem_path, 'r') as f:
        source = f.read()

    # Detect language from extension
    ext = Path(problem_path).suffix
    lang_map = {'.py': 'python', '.c': 'c', '.java': 'java', '.js': 'javascript'}
    language = lang_map.get(ext, 'python')

    # Parse code and build AST index
    reg = make_registry()
    wrapper = reg.get_wrapper(language)
    parser = TreeSitterCodeParser({language: wrapper})
    parsed = parser.parse(source, language)

    extractor = AstExtractor(keep_unnamed=False, text_limit=120)
    nodes, edges = extractor.extract(parsed, wrapper)
    index = build_ast_index(nodes, edges)

    # Build CFG
    print(f"Building CFG...")
    cfg = build_cfg(index)
    print(f"  - Call Sites: {len(cfg.call_sites)}")
    print(f"  - Functions: {len(cfg.functions)}")

    # Build Def-Use Graph
    print(f"Building Def-Use Graph...")
    dug = build_def_use(index)
    print(f"  - Defs: {len(dug.defs)}")
    print(f"  - Uses: {len(dug.uses)}")

    # Generate CFG visualization (detailed mode - shows actual control flow)
    cfg_output = output_dir / f"{problem_name}_cfg.png"
    print(f"Generating CFG visualization (detailed): {cfg_output.name}")
    visualize_cfg(cfg, index, output_path=str(cfg_output), format="png", view=False, view_mode="detailed")

    # Generate Def-Use visualization
    defuse_output = output_dir / f"{problem_name}_defuse.png"
    print(f"Generating Def-Use visualization: {defuse_output.name}")
    visualize_def_use(dug, index, output_path=str(defuse_output), format="png", view=False)

    print(f"✓ Completed: {problem_name}")


def main():
    """Main execution function."""
    # Setup paths
    script_dir = Path(__file__).parent
    problems_dir = script_dir.parent / "problems"
    output_dir = script_dir.parent / "results"

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define problems to visualize
    problems = [
        {
            "path": problems_dir / "humaneval" / "problem_001.py",
            "name": "humaneval_001_separate_paren_groups"
        },
        {
            "path": problems_dir / "humaneval_plus" / "problem_010.py",
            "name": "humaneval_plus_010_make_palindrome"
        },
        {
            "path": problems_dir / "apps_medium" / "problem_fibonacci.py",
            "name": "apps_medium_fibonacci"
        }
    ]

    print("="*60)
    print("CFG and Def-Use Graph Visualization")
    print("="*60)
    print(f"Output directory: {output_dir}")

    # Process each problem
    for problem in problems:
        try:
            visualize_problem(
                str(problem["path"]),
                problem["name"],
                output_dir
            )
        except Exception as e:
            print(f"✗ Error processing {problem['name']}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("All visualizations completed!")
    print(f"Results saved to: {output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
