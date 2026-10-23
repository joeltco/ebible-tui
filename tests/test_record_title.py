"""The review recorder produces deterministic, real app frames without services."""

import importlib.util
import json
from pathlib import Path


async def test_recorded_entrance_and_opening_sequence(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('record_title', 'tools/record_title.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    converted = []
    monkeypatch.setattr(module, 'make_gif', lambda out, frames: converted.append((out, frames)))
    out = tmp_path / 'frames'
    await module.record(out, 'parchment', gif=True)
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['theme'] == 'parchment'
    assert manifest['size'] == [50, 30] and manifest['interval_ms'] == 50
    frames = manifest['frames']
    assert len(frames) == 52
    assert len(list(out.glob('*.svg'))) == 52
    assert frames[0]['progress'] < 0.001 and frames[16]['progress'] == 1
    opening = [frame for frame in frames if frame['stage'] == 'opening']
    assert opening[6]['wipe_offset'] == 25
    assert frames[-1]['stage'] == 'reader'
    assert converted == [(out, [frame['file'] for frame in frames])]
    assert 'መጽሐፍ' in (out / frames[20]['file']).read_text(encoding='utf-8')
    assert 'Genesis' in (out / frames[-1]['file']).read_text(encoding='utf-8')
    assert Path('tools/measure_startup.py').is_file()
