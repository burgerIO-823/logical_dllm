CFG = {
    # ……你原来的 7 类……
    "function_def_types": ["function_declaration", "method_definition", "generator_function", "arrow_function"],
    "assignment_types":   ["assignment_expression", "variable_declarator"],
    "identifier_types":   ["identifier"],
    "if_types":           ["if_statement", "else_clause"],
    "loop_types":         ["for_statement", "while_statement", "do_statement", "for_in_statement", "for_of_statement"],
    "call_types":         ["call_expression", "new_expression", "await_expression"],
    "return_types":       ["return_statement"],

    # 结构类
    "root_types":      ["program"],
    "block_types":     ["statement_block"],
    "paramlist_types": ["formal_parameters"],

    # 表达式类
    "compare_expr_types": ["binary_expression"],
    "paren_expr_types":   ["parenthesized_expression"],
    # 若需要整数字面量，可再加 literal_int_types（取决于 tree-sitter-javascript 的节点名，比如 "number"）
}