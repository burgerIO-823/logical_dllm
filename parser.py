class ParsedCode:
    def __init__(self, language: str, ast_root, source: str):
        self.language = language
        self.ast_root = ast_root  # tree-sitter Node
        self.source = source

class CodeParser:
    def parse(self, code: str, language: str) -> ParsedCode:
        raise NotImplementedError

class TreeSitterCodeParser(CodeParser):
    def __init__(self, language_configs):
        # language_configs: dict[language_name -> TreeSitterLanguageWrapper]
        self.languages = language_configs

    def parse(self, code: str, language: str) -> ParsedCode:
        lang = self.languages[language]
        tree = lang.parser.parse(code.encode("utf8"))
        return ParsedCode(language, tree.root_node, code)
