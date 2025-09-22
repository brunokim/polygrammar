import re


def make_escapes_pattern(escapes):
    return "|".join(re.escape(key) for key in escapes)


def replace_escapes(pattern, escapes, text):
    def repl(m):
        ch = m.group()
        return escapes.get(ch, ch)

    return re.sub(pattern, repl, text)


def reverse_escapes(escapes):
    return {esc: ch for ch, esc in escapes.items()}


SLASH_ESCAPES = {
    "\\": r"\\",
    "\n": r"\n",
    "\r": r"\r",
    "\t": r"\t",
    "\f": r"\f",
    "\v": r"\v",
}
