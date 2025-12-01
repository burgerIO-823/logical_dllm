CFG = {
    # ……原来的 7 类……
    "function_def_types": ["method_declaration", "constructor_declaration", "compact_constructor_declaration"],
    "assignment_types":   ["assignment_expression", "variable_declarator"],
    "identifier_types":   ["identifier", "type_identifier"],
    "if_types":           ["if_statement"],
    "loop_types":         ["for_statement", "while_statement", "enhanced_for_statement", "do_statement"],
    "call_types":         ["method_invocation", "object_creation_expression", "super_invocation", "this_invocation"],
    "return_types":       ["return_statement"],

    # 结构类
    "root_types":       ["program"],
    "block_types":      ["block", "class_body","constructor_body"],
    "paramlist_types":  ["formal_parameters"],
    "paramdecl_types":  ["formal_parameter"],
    "class_def_types":  ["class_declaration"],

    # 类型类
    "type_spec_types":  ["integral_type"],
    "attr_access_types": ["field_access", "scoped_identifier"],
}