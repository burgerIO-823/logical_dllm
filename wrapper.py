from tree_sitter import Language, Parser

class TreeSitterLanguageWrapper:
    def __init__(self, lib_path: str, language_name: str, config: dict = None):
        self.language = Language(lib_path, language_name)
        self.parser = Parser()
        self.parser.set_language(self.language)
        self.config = config or {}
