#!/usr/bin/env python3
"""Headless smoke skeleton; batch 2 adds visits to every reader screen."""

import argparse
import asyncio
from pathlib import Path

from ebible.app import EBibleApp


async def smoke(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for width, height in ((50, 30), (120, 40)):
        app = EBibleApp()
        async with app.run_test(size=(width, height)) as pilot:
            await pilot.pause()
            card = app.query_one('#placeholder')
            assert card.region.right <= width, 'Placeholder clipped horizontally'
            assert card.region.bottom <= height - 1, 'Placeholder clipped vertically'
            assert card.virtual_size.width <= card.size.width, 'Horizontal overflow'
            path = app.save_screenshot(f'ebible-{width}x{height}.svg', path=str(out))
            print(f'{width}x{height}: OK — {path}')
            await pilot.click('#quit')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(smoke(args.out))


if __name__ == '__main__':
    main()
