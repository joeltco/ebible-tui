"""Console entry point: `ebible`."""

from __future__ import annotations

import sys

from ebible.data.store import StoreError


def main() -> int:
    from ebible.ui.app import run

    try:
        run()
    except StoreError as exc:
        print(f'ebible: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
