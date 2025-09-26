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
        if self.serializer_pattern is None:
            return text
        return re.sub(self.serializer_pattern, self.serializer_replacer, text)

    def parse(self, text):
        return re.sub(self.parser_pattern, self.parser_replacer, text)


class EnumeratedSet(Escape):
    def __init__(self, mapping):
        self.mapping = mapping
        self.reversed_mapping = {v: k for k, v in mapping.items()}

        serializer_pattern = "|".join(re.escape(k) for k in self.mapping)
        parser_pattern = "|".join(re.escape(v) for v in self.reversed_mapping)
        super().__init__(serializer_pattern, parser_pattern)

    def serializer_replacer(self, m):
        return self.mapping[m.group()]

    def parser_replacer(self, m):
        return self.reversed_mapping[m.group()]


class DuplicateQuote(EnumeratedSet):
    def __init__(self, quote):
        super().__init__({quote: quote + quote})


class SingleCharBackslash(EnumeratedSet):
    def __init__(self, char_escapes):
        for ch, escape in char_escapes.items():
            if len(ch) != 1 or len(escape) != 1:
                raise ValueError(
                    "char_escapes must map single characters to single characters, got {ch!r}: {escape!r}"
                )
        super().__init__({ch: "\\" + escape for ch, escape in char_escapes.items()})


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
        code_str = m.group(1)
        code = int(code_str, base=16)
        return chr(code)


class UnknownSingleCharBackslash(Escape):
    def __init__(self, unknown_escapes="remove_slash"):
        if unknown_escapes not in {"ignore", "remove_slash", "error"}:
            raise ValueError(
                "unknown_escapes must be one of 'ignore', 'remove_slash', or 'error'"
            )
        self.unknown_escapes = unknown_escapes
        super().__init__(None, r"\\(.)")

    def parser_replacer(self, m):
        if self.unknown_escapes == "ignore":
            return m.group()
        if self.unknown_escapes == "error":
            raise ValueError(f"Unknown escape sequence: {m.group()!r}")
        assert self.unknown_escapes == "remove_slash"
        ch = m.group(1)
        return ch


class CombinedEscapes(Escape):
    def __init__(self, sub_escapes):
        self.sub_escapes = sub_escapes
        serializer_pattern = "|".join(
            e.serializer_pattern
            for e in self.sub_escapes
            if e.serializer_pattern is not None
        )
        parser_pattern = "|".join(e.parser_pattern for e in self.sub_escapes)
        super().__init__(serializer_pattern, parser_pattern)

    def serializer_replacer(self, m):
        text = m.group()
        for e in self.sub_escapes:
            if e.serializer_pattern is None:
                continue
            m = re.match(e.serializer_pattern, text)
            if m is not None:
                return e.serializer_replacer(m)
        raise Exception("Should not be reached: {text!r} did not match any sub-escape")

    def parser_replacer(self, m):
        text = m.group()
        for e in self.sub_escapes:
            m = re.match(e.parser_pattern, text)
            if m is not None:
                return e.parser_replacer(m)
        raise Exception("Should not be reached: {text!r} did not match any sub-escape")


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
UNICODE_BACKSLASH_ESCAPE = CombinedEscapes(
    [
        Unicode8CharacterCode(),
        Unicode16CharacterCode(),
        Unicode32CharacterCode(),
        UnknownSingleCharBackslash(unknown_escapes="remove_slash"),
    ]
)
