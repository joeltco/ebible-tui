"""Command-line entry point; --version does not import Textual or optional SDKs."""

import argparse
from collections.abc import Sequence

from ebible import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='ebible', description='The 81-book Ethiopian Orthodox Bible'
    )
    parser.add_argument('reference', nargs='*', metavar='REF', help='e.g. "john 3:16" or "ዘፍ 1"')
    parser.add_argument('--version', action='version', version=f'ebible {__version__}')
    parser.add_argument(
        '--theme',
        metavar='NAME',
        help='Theme: meskel, tewahedo, parchment, lalibela, midnight, high-contrast, or a Textual built-in',
    )
    args = parser.parse_args(argv)

    from ebible.core.refs import parse_reference
    from ebible.core.scripture import ScriptureStore

    try:
        reference = (
            parse_reference(' '.join(args.reference), validate=ScriptureStore().validate_reference)
            if args.reference
            else None
        )
        from ebible.app import EBibleApp

        app = EBibleApp(reference=reference, theme_name=args.theme)
    except ValueError as exc:
        parser.error(str(exc))
    app.run()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
