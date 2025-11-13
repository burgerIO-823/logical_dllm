CFG = {
    # ……你原来的 7 类保持不动……
    "function_def_types": ["function_definition"],
    "class_def_types":    ["class_definition"],
    "assignment_types":   ["assignment", "augmented_assignment", "annotated_assignment"],
    "identifier_types":   ["identifier"],
    "if_types":           ["if_statement", "elif_clause", "else_clause"],
    "loop_types":         ["for_statement", "while_statement"],
    "call_types":         ["call", "await"],
    "return_types":       ["return_statement"],

    # 新增结构类
    "root_types":      ["module"],
    "block_types":     ["block"],
    "paramlist_types": ["parameters"],

    # 新增表达式/类型类（可选，但能让 comparison_operator / integer 不再是纯 other）
    "compare_expr_types": ["comparison_operator"],
    "literal_int_types":  ["integer"],

    "attr_access_types": ["attribute"],
}