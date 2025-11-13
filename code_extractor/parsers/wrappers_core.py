from typing import Dict, Any, Optional
from tree_sitter import Language, Parser

class TreeSitterLanguageWrapper:
    def __init__(self, language: Language, config: Optional[Dict[str, Any]] = None):
        self.language = language
        self.parser = Parser(language)  # 新 API
        self.config = config or {}

    @property
    def kinds(self) -> Dict[str, set]:
        cfg = self.config

        def s(key: str) -> set:
            return set(cfg.get(key, []))

        return {
            # —— 原来的 7 类：控制 / 语义节点 —— #
            "function_def": s("function_def_types"),
            "assignment":   s("assignment_types"),
            "identifier":   s("identifier_types"),
            "if_stmt":      s("if_types"),
            "loop_stmt":    s("loop_types"),
            "call_expr":    s("call_types"),
            "return_stmt":  s("return_types"),

            # —— 新增：结构节点（你现在关心的） —— #
            # 顶层根节点：module / program / translation_unit
            "root":        s("root_types"),
            # 语句块：block / statement_block / compound_statement / class_body
            "block":       s("block_types"),
            # 参数列表：parameters / formal_parameters / parameter_list
            "param_list":  s("paramlist_types"),
            # 参数声明：parameter_declaration / formal_parameter
            "param_decl":  s("paramdecl_types"),
            # 类定义：class_declaration
            "class_def":   s("class_def_types"),

            # —— 新增：表达式/类型类（可选，用于更细粒度依赖） —— #
            # 比较 or 条件表达式：comparison_operator / binary_expression（a > 0）
            "compare_expr": s("compare_expr_types"),
            # 括号表达式：(a > 0)
            "paren_expr":   s("paren_expr_types"),
            # 整数字面量：integer / decimal_integer_literal / 等
            "literal_int":  s("literal_int_types"),
            # 类型标注：primitive_type / integral_type 等
            "type_spec":    s("type_spec_types"),
            
            "attr_access": s("attr_access_types"),
        }