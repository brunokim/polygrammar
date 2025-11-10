if __name__ == "__main__":
    from argparse import ArgumentParser

    p = ArgumentParser()
    p.add_argument(
        "-g", "--grammar-language", choices=["lisp", "abnf", "ebnf"], default="ebnf"
    )
    p.add_argument("text")

    args = p.parse_args()

    match args.grammar_language:
        case "lisp":
            from polygrammar.grammars.lisp import parse_lisp

            parser = parse_lisp
        case "abnf":
            from polygrammar.grammars.abnf import parse_abnf

            parser = parse_abnf
        case "ebnf":
            from polygrammar.grammars.ebnf import parse_ebnf

            parser = parse_ebnf

    print(parser(args.text))
