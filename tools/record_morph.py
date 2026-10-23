#!/usr/bin/env python3
"""Record actual 50×30 reader SVGs at 50ms animation-time steps, without network IO.

Uses real Genesis 1:1 Amharic and caller-supplied English (a labelled fixture by default).
The deterministic clock makes the resulting sequence suitable for a 20fps GIF,
independent of how long SVG rendering takes on the recording host.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ebible.app import EBibleApp
from ebible.core.models import VerseRef
from ebible.core.translate.service import TranslationService
from ebible.ui.widgets.verse_view import VerseView

FIXTURE = 'Recording fixture: English replaces Amharic here.'
STEP = 0.05


async def record(out: Path, theme: str = 'meskel', text: str = FIXTURE) -> None:
    out.mkdir(parents=True, exist_ok=True)
    frames: list[dict[str, object]] = []
    release = asyncio.Event()

    async def fake(service: TranslationService, ref: VerseRef) -> str:
        await release.wait()
        return text

    with TemporaryDirectory(prefix='ebible-morph-') as temporary:
        with (
            patch.dict(
                os.environ,
                {'XDG_CONFIG_HOME': temporary + '/config', 'XDG_DATA_HOME': temporary + '/data'},
            ),
            patch.object(TranslationService, 'translate_verse', fake),
        ):
            os.environ.pop('NO_COLOR', None)
            os.environ.pop('ANTHROPIC_API_KEY', None)
            app = EBibleApp(theme_name=theme)
            async with app.run_test(size=(50, 30)) as pilot:
                await app.ready.wait()
                view = app.reader.query_one(VerseView)
                clock = [100.0]
                view.clock = lambda: clock[0]
                assert view.motion_timer is not None
                view.motion_timer.pause()
                with patch.object(view, '_wake_timer', lambda: None):

                    async def capture(stage: str) -> None:
                        view.tick()
                        await pilot.pause()
                        name = f'frame-{len(frames):04d}.svg'
                        (out / name).write_text(app.export_screenshot(), encoding='utf-8')
                        verse = app.scripture.verse(VerseRef(1))
                        state = view.morphs[verse.ref]
                        frames.append(
                            {
                                'file': name,
                                'time_ms': len(frames) * 50,
                                'stage': stage,
                                'flourish': state.flourish(clock[0]),
                                'reveal_index': state.index(clock[0], verse.text_am, text),
                            }
                        )
                        clock[0] = 100 + len(frames) * STEP

                    await capture('amharic')
                    await app.toggle_translation(VerseRef(1))
                    for _ in range(14):
                        await capture('shimmer')
                    release.set()
                    await app.workers.wait_for_complete()
                    for _ in range(21):
                        await capture('forward')
                    for _ in range(6):
                        await capture('flourish')
                    for _ in range(4):
                        await capture('english')
                    await app.toggle_translation(VerseRef(1))
                    for _ in range(21):
                        await capture('reverse')
                    for _ in range(4):
                        await capture('amharic')
    (out / 'manifest.json').write_text(
        json.dumps(
            {
                'fps': 20,
                'interval_ms': 50,
                'size': [50, 30],
                'theme': theme,
                'reference': 'Genesis 1:1',
                'fixture': text == FIXTURE,
                'frames': frames,
            },
            indent=2,
        )
        + '\n',
        encoding='utf-8',
    )
    print(f'{len(frames)} SVG frames · 50 ms per frame · 50×30 · {out.resolve()}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--theme', default='meskel')
    parser.add_argument(
        '--text', default=FIXTURE, help='English to reveal; defaults to labelled fixture'
    )
    args = parser.parse_args()
    asyncio.run(record(args.out, args.theme, args.text))
