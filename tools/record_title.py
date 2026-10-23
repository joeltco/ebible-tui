#!/usr/bin/env python3
"""Record the real cover/reader at 50 ms steps; optionally rasterize a review GIF.

SVG recording needs only the app's dependencies. --gif additionally needs the
system rsvg-convert and ImageMagick magick commands (nothing is installed).
"""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ebible.app import EBibleApp
from ebible.ui.screens.title import TitleScreen


async def record(out: Path, theme: str = 'meskel', *, gif: bool = False) -> None:
    out.mkdir(parents=True, exist_ok=True)
    frames: list[dict[str, object]] = []
    with TemporaryDirectory(prefix='ebible-cover-') as temporary:
        with patch.dict(
            os.environ,
            {'XDG_CONFIG_HOME': temporary + '/config', 'XDG_DATA_HOME': temporary + '/data'},
        ):
            os.environ.pop('NO_COLOR', None)
            app = EBibleApp(theme_name=theme)
            async with app.run_test(size=(50, 30)) as pilot:
                await app.ready.wait()
                title = app.screen
                assert isinstance(title, TitleScreen)
                clock = [100.0]
                title.clock = lambda: clock[0]
                title.started = 100.0
                title.phase = 'entrance'
                assert title.motion_timer is not None
                title.motion_timer.pause()

                async def capture(stage: str) -> None:
                    title.tick()
                    await pilot.pause()
                    name = f'frame-{len(frames):04d}.svg'
                    (out / name).write_text(app.export_screenshot(), encoding='utf-8')
                    frames.append(
                        {
                            'file': name,
                            'time_ms': len(frames) * 50,
                            'stage': stage,
                            'progress': title.progress,
                            'wipe_offset': title.wipe_offset,
                        }
                    )

                for step in range(17):
                    clock[0] = 100 + step * 0.05
                    await capture('entrance')
                for _ in range(12):
                    await capture('cover')
                await title.activate()
                title.motion_timer.pause()
                for step in range(13):
                    clock[0] = title.started + step * 0.05
                    await capture('opening')
                for _ in range(10):
                    await capture('reader')
    (out / 'manifest.json').write_text(
        json.dumps(
            {'size': [50, 30], 'theme': theme, 'interval_ms': 50, 'frames': frames}, indent=2
        )
        + '\n',
        encoding='utf-8',
    )
    if gif:
        await asyncio.to_thread(make_gif, out, [str(frame['file']) for frame in frames])
    print(f'{len(frames)} SVG frames · 50 ms · {theme} · {out.resolve()}')


def make_gif(out: Path, frames: list[str]) -> None:
    rasterizer, magick = shutil.which('rsvg-convert'), shutil.which('magick')
    if not rasterizer or not magick:
        raise RuntimeError(
            'GIF rendering needs rsvg-convert and ImageMagick magick; SVG frames are saved.'
        )
    with TemporaryDirectory(prefix='ebible-cover-png-') as temporary:
        pngs = []
        for index, frame in enumerate(frames):
            png = str(Path(temporary) / f'{index:04d}.png')
            subprocess.run(
                [rasterizer, '-o', png, str(out / frame)], check=True, capture_output=True
            )
            pngs.append(png)
        subprocess.run(
            [
                magick,
                '-delay',
                '5',
                '-loop',
                '0',
                *pngs,
                '-layers',
                'Optimize',
                str(out / 'title.gif'),
            ],
            check=True,
            capture_output=True,
        )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--theme', default='meskel')
    parser.add_argument('--gif', action='store_true')
    args = parser.parse_args()
    asyncio.run(record(args.out, args.theme, gif=args.gif))
