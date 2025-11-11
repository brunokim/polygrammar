# Polygrammar

Polyglot grammar library: convert between grammar languages.

Goal: to convert between **ABNF**, **ANTLR4**, **Lark** and **Tatsu** grammar
languages without losses, provided enough configuration to translate between
different semantics (e.g., ordered alternatives).

Current status: convert between internal grammar languages and ABNF.

## Developing

### Organization

- `grammars.escapes`: char-to-string serialization and parsing.
- `model`: base model and pure functions for grammar intermediate representation (IR).
- `grammars.python_re_writer`: write grammar model as Python's `re` regex syntax.
- `optimizer`: optimize grammar-to-grammar
- `runtime`: combine grammar and visitor class into an efficient runtime representation.
- `recursive_parser`: grammar parser implementation using top-down recursive descent.
- `generate`: generate text from grammar model.
- `grammars.lisp`: parse and serialize grammar IR in a Lisp language.
- `grammars.ebnf`: parse and serialize grammar IR in an EBNF-like language.
- `grammars.abnf`: parse and serialize grammar IR in a standard ABNF language.


```dot
digraph {
    grammars.escapes;
    model;

    grammars.python_re_writer -> grammars.escapes
    grammars.python_re_writer -> model

    optimizer -> grammars.python_re_writer
    optimizer -> model

    runtime -> model
    runtime -> optimizer

    recursive_parser -> model
    recursive_parser -> runtime

    generate -> model
    generate -> recursive_parser

    grammars.lisp -> model
    grammars.lisp -> grammars.escapes
    grammars.lisp -> recursive_parser

    grammars.ebnf -> grammars.escapes
    grammars.ebnf -> grammars.lisp
    grammars.ebnf -> model
    grammars.ebnf -> recursive_parser

    grammars.abnf -> grammars.lisp
    grammars.abnf -> model
    grammars.abnf -> recursive_parser
}
```
