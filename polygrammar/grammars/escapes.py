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


class FiniteSet(Escape):
    def __init__(self, escapes):
        self.escapes = escapes
        self.reversed_escapes = {escape: text for text, escape in escapes.items()}

        serializer_pattern = "|".join(re.escape(text) for text in escapes)
        parser_pattern = "|".join(re.escape(escape) for escape in escapes.values())
        super().__init__(serializer_pattern, parser_pattern)

    def serializer_replacer(self, m):
        text = m.group()
        if escape := self.escapes.get(text):
            return escape
        return text

    def parser_replacer(self, m):
        escape = m.group()
        if text := self.reversed_escapes.get(escape):
            return text
        return escape


class DuplicateQuote(FiniteSet):
    def __init__(self, quote):
        super().__init__({quote: quote + quote})


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


DUPLICATE_DOUBLE_QUOTE_ESCAPE = DuplicateQuote('"')
DUPLICATE_SINGLE_QUOTE_ESCAPE = DuplicateQuote("'")
SINGLE_CHAR_SLASH_ESCAPE = FiniteSet(
    {
        "\\": r"\\",
        "\a": r"\a",
        "\b": r"\b",
        "\f": r"\f",
        "\n": r"\n",
        "\r": r"\r",
        "\t": r"\t",
        "\v": r"\v",
    }
)
