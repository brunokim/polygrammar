import re

from attrs import field, frozen
from attrs.validators import deep_iterable, instance_of, min_len


@frozen
class Escape:
    _serializer_pattern: str = field(init=False)
    _parser_pattern: str = field(init=False)

    def _set_patterns(self, serializer_pattern, parser_pattern):
        object.__setattr__(self, "_serializer_pattern", serializer_pattern)
        object.__setattr__(self, "_parser_pattern", parser_pattern)

    def serialize(self, text):
        return re.sub(self._serializer_pattern, self.serializer_replacer, text)

    def parse(self, text):
        return re.sub(self._parser_pattern, self.parser_replacer, text)


@frozen
class FiniteSet(Escape):
    escapes: dict = field(validator=instance_of(dict))

    _reversed_escapes: dict = field(init=False, factory=dict)

    def __attrs_post_init__(self):
        serializer_pattern = "|".join(re.escape(text) for text in self.escapes)
        parser_pattern = "|".join(re.escape(escape) for escape in self.escapes.values())
        self._set_patterns(serializer_pattern, parser_pattern)

        for text, escape in self.escapes.items():
            self._reversed_escapes[escape] = text

    def serializer_replacer(self, m):
        text = m.group()
        if escape := self.escapes.get(text):
            return escape
        return text

    def parser_replacer(self, m):
        escape = m.group()
        if text := self._reversed_escapes.get(escape):
            return text
        return escape


@frozen
class DuplicateQuote(FiniteSet):
    def __init__(self, quote):
        super().__init__({quote: quote + quote})


@frozen
class CombinedEscapes(Escape):
    sub_escapes: tuple[Escape, ...] = field(
        converter=tuple, validator=[min_len(2), deep_iterable(instance_of(Escape))]
    )

    def __attrs_post_init__(self):
        serializer_pattern = "|".join(e._serializer_pattern for e in self.sub_escapes)
        parser_pattern = "|".join(e._parser_pattern for e in self.sub_escapes)
        self._set_patterns(serializer_pattern, parser_pattern)

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
