#!/usr/bin/env python3
"""Measure first meaningful headless frame in fresh processes (including imports).

Set PYTHONPATH to a baseline src directory to run the same probe against it.
Excludes terminal transport and the Python interpreter's own process startup.
"""

import time

STARTED = time.perf_counter()

import argparse  # noqa: E402
import asyncio  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import statistics  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402
from tempfile import TemporaryDirectory  # noqa: E402


async def sample() -> None:
    from ebible.app import EBibleApp

    first: list[float] = []

    class Probe(EBibleApp):
        CSS_PATH = str(
            Path(sys.modules[EBibleApp.__module__].__file__).parent / 'ui/styles/app.tcss'
        )

        def _display(self, screen, renderable):
            super()._display(screen, renderable)
            if not first and renderable is not None:
                meaningful = type(screen).__name__ == 'TitleScreen' or (
                    type(screen).__name__ == 'ReaderScreen' and screen.chapter_data is not None
                )
                if meaningful:
                    first.append((time.perf_counter() - STARTED) * 1000)

    with TemporaryDirectory(prefix='ebible-startup-') as temporary:
        os.environ['XDG_CONFIG_HOME'] = temporary + '/config'
        os.environ['XDG_DATA_HOME'] = temporary + '/data'
        os.environ.pop('NO_COLOR', None)
        app = Probe()
        async with app.run_test(size=(50, 30)) as pilot:
            await asyncio.wait_for(app.ready.wait(), 5)
            await pilot.pause()
    assert first, 'No meaningful frame was drawn'
    print(json.dumps(first[0]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', action='store_true')
    parser.add_argument('--runs', type=int, default=12)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.sample:
        asyncio.run(sample())
        return
    values = []
    for _ in range(args.runs):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), '--sample'],
            check=True,
            capture_output=True,
            encoding='utf-8',
        )
        values.append(json.loads(result.stdout))
    report = (
        json.dumps(
            {
                'size': [50, 30],
                'milliseconds': values,
                'median_ms': statistics.median(values),
                'max_ms': max(values),
            },
            indent=2,
        )
        + '\n'
    )
    if args.out:
        args.out.write_text(report, encoding='utf-8')
    print(report, end='')


if __name__ == '__main__':
    main()
