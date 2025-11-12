from typing import Dict, Any, Optional
from tree_sitter import Language, Parser

class TreeSitterLanguageWrapper:
    def __init__(self, language: Language, config: Optional[Dict[str, Any]] = None):
        self.language = language
        self.parser = Parser(language)  # 新 API
        self.config = config or {}

    @property
    def kinds(self) -> Dict[str, set]:
        return {
            "function_def": set(self.config.get("function_def_types", [])),
            "assignment":   set(self.config.get("assignment_types", [])),
            "identifier":   set(self.config.get("identifier_types", [])),
            "if_stmt":      set(self.config.get("if_types", [])),
            "loop_stmt":    set(self.config.get("loop_types", [])),
            "call_expr":    set(self.config.get("call_types", [])),
            "return_stmt":  set(self.config.get("return_types", [])),
        }