from pathlib import Path
from code_extractor.parsers.registry import LanguageRegistry, LangMeta
from code_extractor.configs import python, javascript, c, java

# code_extractor/ 目录
ROOT = Path(__file__).resolve().parents[1]

# 你的 .so/.dylib 现在在 code_extractor/langs/build
LIB_DIRS = [
    ROOT / "langs" / "build",   # 首选：你当前的实际位置
    ROOT / "build",             # 兼容：如果以后你把库直接放在 build/
]

def lp(name: str) -> Path:
    for d in LIB_DIRS:
        p = d / f"{name}.so"
        if p.exists():
            return p
        # macOS 下也可能是 .dylib
        p2 = d / f"{name}.dylib"
        if p2.exists():
            return p2
    # 如果都没找到，就返回默认路径（让注册表抛 FileNotFoundError）
    return (ROOT / "langs" / "build" / f"{name}.so")

def make_registry() -> LanguageRegistry:
    reg = LanguageRegistry()
    reg.register_meta(LangMeta(
        name="python",
        lib_path=lp("python"),
        config=python.CFG,
        grammar_version="tree-sitter-python 0.21",
        api_version="LANGUAGE_VERSION=15",
        notes="Core Python grammar",
    ))
    reg.register_meta(LangMeta(
        name="javascript",
        lib_path=lp("javascript"),
        config=javascript.CFG,
        grammar_version="tree-sitter-javascript 0.21",
        api_version="LANGUAGE_VERSION=15",
    ))
    reg.register_meta(LangMeta(
        name="c",
        lib_path=lp("c"),
        config=c.CFG,
    ))
    reg.register_meta(LangMeta(
        name="java",
        lib_path=lp("java"),
        config=java.CFG,
    ))
    return reg

if __name__ == "__main__":
    reg = make_registry()
    print("Registered languages:", reg.list_languages())