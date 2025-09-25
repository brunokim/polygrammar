import re


class Escape:
    def __init__(self, serializer_pattern, parser_pattern):
        self.serializer_pattern = serializer_pattern
        self.parser_pattern = parser_pattern

    def serializer_replacer(self, m):
        raise NotImplementedError(
            f"{type(self).__name__}.serializer_replacer not implemented"
        )

    def parser_replacer(self, m):
        raise NotImplementedError(
            f"{type(self).__name__}.parser_replacer not implemented"
        )

    def serialize(self, text):
        return re.sub(self.serializer_pattern, self.serializer_replacer, text)

    def parse(self, text):
        return re.sub(self.parser_pattern, self.parser_replacer, text)


class DuplicateQuote(Escape):
    def __init__(self, quote):
        self.quote = quote
        super().__init__(re.escape(quote), re.escape(quote + quote))

    def serializer_replacer(self, m):
        ch = m.group()
        if ch == self.quote:
            return self.quote + self.quote
        return ch

    def parser_replacer(self, m):
        text = m.group()
        if text == self.quote + self.quote:
            return self.quote
        return text


class SingleCharBackslash(Escape):
    def __init__(self, char_escapes, unknown_escapes="remove_slash"):
        if unknown_escapes not in {"ignore", "error", "remove_slash"}:
            raise ValueError(
                "unknown_escapes must be one of 'ignore', 'error', or 'passthrough'"
            )
        self.unknown_escapes = unknown_escapes

        self.escapes = {ch: "\\" + escape for ch, escape in char_escapes.items()}
        self.reversed_escapes = {escape: ch for ch, escape in self.escapes.items()}

        super().__init__(r"(?s:.)", r"\\(.)")

    def serializer_replacer(self, m):
        ch = m.group()
        if escape := self.escapes.get(ch):
            return escape
        return ch

    def parser_replacer(self, m):
        escape = m.group()
        if ch := self.reversed_escapes.get(escape):
            return ch
        if escape[0] != "\\":
            return escape

        match self.unknown_escapes:
            case "ignore":
                return escape
            case "error":
                raise ValueError(f"Unknown escape sequence: {escape!r}")
            case "remove_slash":
                return escape[1]


class OctalCharacterCode(Escape):
    def __init__(self):
        super().__init__(r"[\x00-\x1F\x7F-\x9F]", r"\\([0-7]{3})")

    def serializer_replacer(self, m):
        ch = m.group()
        return rf"\{ord(ch):03o}"

    def parser_replacer(self, m):
        code_str = m.group(1)
        code = int(code_str, base=8)
        return chr(code)


class Unicode8CharacterCode(Escape):
    def __init__(self):
        super().__init__(r"[\x00-\x1F\x7F-\x9F]", r"\\x([0-9a-fA-F]{2})")

    def serializer_replacer(self, m):
        ch = m.group()
        return rf"\x{ord(ch):02x}"

    def parser_replacer(self, m):
        if not m.group().startswith("\\x"):
            return m.group()
        code_str = m.group(1)
        code = int(code_str, base=16)
        return chr(code)


class Unicode16CharacterCode(Escape):
    def __init__(self):
        super().__init__(r"[\u0100-\uFFFF]", r"\\u([0-9a-fA-F]{4})")

    def serializer_replacer(self, m):
        ch = m.group()
        return rf"\u{ord(ch):04x}"

    def parser_replacer(self, m):
        if not m.group().startswith("\\u"):
            return m.group()
        code_str = m.group(1)
        code = int(code_str, base=16)
        return chr(code)


class Unicode32CharacterCode(Escape):
    def __init__(self):
        super().__init__(r"[\U00010000-\U0010FFFF]", r"\\U([0-9a-fA-F]{8})")

    def serializer_replacer(self, m):
        ch = m.group()
        return rf"\U{ord(ch):08x}"

    def parser_replacer(self, m):
        if not m.group().startswith("\\U"):
            return m.group()
        code_str = m.group(1)
        code = int(code_str, base=16)
        return chr(code)


class CombinedEscapes(Escape):
    def __init__(self, sub_escapes):
        self.sub_escapes = sub_escapes
        serializer_pattern = "|".join(e.serializer_pattern for e in self.sub_escapes)
        parser_pattern = "|".join(e.parser_pattern for e in self.sub_escapes)
        super().__init__(serializer_pattern, parser_pattern)

    def serializer_replacer(self, m):
        for e in self.sub_escapes:
            repl = e.serializer_replacer(m)
            if repl != m.group():
                return repl
        return m.group()

    def parser_replacer(self, m):
        for e in self.sub_escapes:
            repl = e.parser_replacer(m)
            if repl != m.group():
                return repl
        return m.group()


JSON_SINGLE_CHAR_ESCAPES = {
    "\\": "\\",
    "/": "/",
    '"': '"',
    "\b": "b",
    "\f": "f",
    "\n": "n",
    "\r": "r",
    "\t": "t",
}

PYTHON_SINGLE_CHAR_ESCAPES = {
    "\\": "\\",
    "\a": "a",
    "\b": "b",
    "\f": "f",
    "\n": "n",
    "\r": "r",
    "\t": "t",
    "\v": "v",
}

C_SINGLE_CHAR_ESCAPES = {
    "\\": "\\",
    '"': '"',
    "\a": "a",
    "\b": "b",
    "\x1b": "e",
    "\f": "f",
    "\n": "n",
    "\r": "r",
    "\t": "t",
    "\v": "v",
}

DUPLICATE_DOUBLE_QUOTE_ESCAPE = DuplicateQuote('"')
DUPLICATE_SINGLE_QUOTE_ESCAPE = DuplicateQuote("'")
