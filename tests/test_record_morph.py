"""The recording tool exports only explicitly labelled fixture translations."""

import json
import os
import runpy
import xml.etree.ElementTree as ET

from ebible.core.models import VerseRef


async def test_recording_frames_timeline_privacy_and_xdg_restore(tmp_path, scripture, monkeypatch):
    namespace = runpy.run_path('tools/record_morph.py')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-FAKE-RECORD-NOT-REAL-1234')
    monkeypatch.setenv('NO_COLOR', '1')
    before = dict(os.environ)
    out = tmp_path / 'frames'
    await namespace['record'](out)
    assert dict(os.environ) == before
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['fps'] == 20 and manifest['interval_ms'] == 50
    assert manifest['fixture'] and manifest['size'] == [50, 30]
    frames = manifest['frames']
    assert len(frames) == len(list(out.glob('*.svg'))) == 65
    assert [f['time_ms'] for f in frames] == list(range(0, 3250, 50))
    am = scripture.verse(VerseRef(1)).text_am
    english = namespace['FIXTURE']
    extent = max(len(am), len(english))
    for stage, descending in [('forward', False), ('reverse', True)]:
        indices = [f['reveal_index'] for f in frames if f['stage'] == stage]
        assert len(indices) == 21 and min(indices) == 0 and max(indices) == extent
        assert indices == sorted(indices, reverse=descending)
    for f in frames:
        raw = (out / f['file']).read_text(encoding='utf-8')
        visible = ''.join(
            ''.join(node.itertext())
            for node in ET.fromstring(raw).iter('{http://www.w3.org/2000/svg}text')
        )
        # SVG splits styled runs and wrapped lines into separate text elements.
        compact = ''.join(visible.replace('▊', '').split())
        assert before['ANTHROPIC_API_KEY'] not in raw
        if f['stage'] in ('amharic', 'shimmer'):
            assert ''.join(am.split()) in compact and ''.join(english.split()) not in compact
        if f['stage'] == 'english':
            assert ''.join(english.split()) in compact
            assert ''.join(am.split()) not in compact and '◇' in visible
