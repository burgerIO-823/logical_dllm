CFG = {
    # ……原来的 7 类……
    "function_def_types": ["function_definition"],
    "assignment_types":   ["assignment_expression", "init_declarator", "compound_literal_expression"],
    "identifier_types":   ["identifier"],
    "if_types":           ["if_statement"],
    "loop_types":         ["for_statement", "while_statement", "do_statement"],
    "call_types":         ["call_expression"],
    "return_types":       ["return_statement"],

    # 结构类
    "root_types":       ["translation_unit"],
    "block_types":      ["compound_statement"],
    "paramlist_types":  ["parameter_list"],
    "paramdecl_types":  ["parameter_declaration"],

    # 表达式/类型类
    "compare_expr_types": ["binary_expression"],
    "paren_expr_types":   ["parenthesized_expression"],
    "literal_int_types":  ["integer"],
    "type_spec_types":    ["primitive_type"],
}