"""Morph interactions use a controllable clock and explicitly fake translation output."""

import asyncio
from time import monotonic

import pytest
from rich.style import Style
from textual.widgets import Switch

from ebible.app import EBibleApp
from ebible.core.models import VerseRef
from ebible.core.settings import load_settings
from ebible.core.translate.base import TranslationError
from ebible.ui.morph import FRAME_INTERVAL
from ebible.ui.widgets.verse_view import Paragraph, VerseLine, VerseView

FIXTURE = 'Explicit temporary [bold]literal[/bold] English fixture. ' * 4


@pytest.fixture
async def motion(running_app, monkeypatch):
    app, pilot = running_app
    view = app.reader.query_one(VerseView)
    clock = [100.0]
    view.clock = lambda: clock[0]
    view.motion_timer.pause()
    monkeypatch.setattr(view, '_wake_timer', lambda: None)
    return app, pilot, view, clock


@pytest.mark.parametrize('flow', ['lines', 'paragraph'])
async def test_shimmer_morph_interrupt_reverse_cache_and_single_widget(motion, monkeypatch, flow):
    app, pilot, view, clock = motion
    await app.update_setting('verse_flow', flow)
    verse = app.scripture.verse(VerseRef(1))
    release = asyncio.Event()
    calls = []

    async def fake(service, ref):
        calls.append(ref)
        await release.wait()
        return FIXTURE

    monkeypatch.setattr('ebible.app.TranslationService.translate_verse', fake)
    updates = []
    widget_type = VerseLine if flow == 'lines' else Paragraph
    original = widget_type.update

    def track(widget, *args, **kwargs):
        updates.append(widget.id)
        return original(widget, *args, **kwargs)

    monkeypatch.setattr(widget_type, 'update', track)
    children = list(view.children)
    await pilot.press('enter')
    assert view.body_text(verse).plain == verse.text_am
    assert 'Translating' not in view.line_content(verse).plain
    assert app.translating == {verse.ref}
    clock[0] += 0.4
    updates.clear()
    view.tick()
    assert updates == ['verse-1' if flow == 'lines' else 'paragraph']
    first = view.body_text(verse)
    assert first.spans and first.plain == verse.text_am
    clock[0] += 0.4
    view.tick()
    assert first.spans != view.body_text(verse).spans
    await pilot.press('enter')  # Pending requests still deduplicate.
    assert calls == [verse.ref]
    release.set()
    await app.workers.wait_for_complete()
    start = clock[0]
    state = view.morphs[verse.ref]
    assert state.position(start) == 0
    for fraction in (0.0, 0.25, 0.5):
        clock[0] = start + fraction
        updates.clear()
        view.tick()
        index = int(max(len(FIXTURE), len(verse.text_am)) * fraction)
        assert view.body_text(verse).plain == FIXTURE[:index] + verse.text_am[index:]
        assert updates == ['verse-1' if flow == 'lines' else 'paragraph']
        await pilot.pause()
    current = view.body_text(verse).plain
    await pilot.press('enter')
    assert view.body_text(verse).plain == current
    clock[0] += 0.1
    view.tick()
    assert state.position(clock[0]) == pytest.approx(0.4)
    await pilot.press('enter')  # Reverse the reverse without restarting at an endpoint.
    assert state.position(clock[0]) == pytest.approx(0.4)
    clock[0] += 0.6
    view.tick()
    await pilot.pause()
    assert view.body_text(verse).plain == FIXTURE
    assert '◇ ' in view.verse_text(verse).plain and view.verse_text(verse).plain.startswith(' 1 ')
    assert '\n' not in view.line_content(verse).plain
    assert verse.text_am not in view.line_content(verse).plain
    assert view.body_text(verse).style == app.get_css_variables()['secondary']
    assert not any(
        isinstance(span.style, Style) and span.style.bold for span in view.body_text(verse).spans
    )
    assert list(view.children) == children  # No chapter rebuild during animation or fetch.
    assert not view.active
    updates.clear()
    view.tick()
    assert updates == []
    await pilot.press('enter')
    clock[0] += 1
    view.tick()
    await pilot.pause()
    assert view.body_text(verse).plain == verse.text_am
    selector = '#verse-1' if flow == 'lines' else '#paragraph'
    assert await pilot.click(selector, offset=(8, 0))
    assert not app.translating and calls == [verse.ref]
    clock[0] += 0.5
    view.tick()
    assert state.position(clock[0]) == 0.5


async def test_rewrap_growth_and_reverse_without_replacing_widgets(motion, monkeypatch):
    app, pilot, view, clock = motion

    async def fake(service, ref):
        return FIXTURE

    monkeypatch.setattr('ebible.app.TranslationService.translate_verse', fake)
    line = view.query_one('#verse-1', VerseLine)
    initial = line.size.height
    await pilot.press('enter')
    await app.workers.wait_for_complete()
    clock[0] += 0.5
    view.tick()
    await pilot.pause()
    middle = line.size.height
    clock[0] += 0.5
    view.tick()
    await pilot.pause()
    assert initial < middle <= line.size.height
    await pilot.press('enter')
    clock[0] += 1
    view.tick()
    await pilot.pause()
    assert view.query_one('#verse-1') is line and line.size.height == initial


async def test_reduce_motion_pending_swap_toggle_and_restart(motion, monkeypatch, terminal_size):
    app, pilot, view, clock = motion
    assert app.settings.reduce_motion is False
    release = asyncio.Event()

    async def fake(service, ref):
        await release.wait()
        return FIXTURE

    monkeypatch.setattr('ebible.app.TranslationService.translate_verse', fake)
    verse = app.scripture.verse(VerseRef(1))
    await pilot.press('enter', 's')
    switch = app.screen.query_one('#setting-reduce_motion', Switch)
    switch.scroll_visible(animate=False)
    await pilot.pause()
    assert await pilot.click(switch)
    await pilot.pause()
    await pilot.press('escape')
    assert app.settings.reduce_motion and load_settings().reduce_motion
    assert 'Translating…' in view.body_text(verse).plain and not view.active
    before = view.body_text(verse)
    clock[0] += 0.5
    view.tick()
    assert view.body_text(verse) == before
    release.set()
    await app.workers.wait_for_complete()
    assert view.body_text(verse).plain == FIXTURE and not view.active
    await pilot.press('enter')
    assert view.body_text(verse).plain == verse.text_am
    await pilot.press('enter')
    assert view.body_text(verse).plain == FIXTURE and not app.translating
    restarted = EBibleApp()
    async with restarted.run_test(size=terminal_size):
        await restarted.ready.wait()
        assert restarted.settings.reduce_motion and not restarted.translations


async def test_error_stops_shimmer_and_restores_source(motion, monkeypatch):
    app, pilot, view, clock = motion
    release = asyncio.Event()

    async def fake(service, ref):
        await release.wait()
        raise TranslationError('Explicit timeout fixture. Press Enter to retry.')

    monkeypatch.setattr('ebible.app.TranslationService.translate_verse', fake)
    verse = app.scripture.verse(VerseRef(1))
    await pilot.press('enter')
    clock[0] += 0.7
    view.tick()
    assert view.active
    release.set()
    await app.workers.wait_for_complete()
    assert not view.active and not app.translating
    assert view.body_text(verse).plain == verse.text_am
    assert 'Press Enter to retry' in view.line_content(verse).plain
    assert '◇' not in view.line_content(verse).plain


async def test_background_completion_resume_theme_and_resize(motion, monkeypatch):
    app, pilot, view, clock = motion

    async def fake(service, ref):
        return FIXTURE

    monkeypatch.setattr('ebible.app.TranslationService.translate_verse', fake)
    verse = app.scripture.verse(VerseRef(1))
    await pilot.press('enter')
    await app.workers.wait_for_complete()
    clock[0] += 0.4
    view.tick()
    await app.update_setting('theme', 'parchment')
    await pilot.resize_terminal(60, 30)
    await pilot.pause()
    assert view.morphs[verse.ref].position(clock[0]) == pytest.approx(0.4)
    assert view.body_text(verse).spans[-1].style == view.colours(verse).muted.hex or len(
        FIXTURE
    ) * 0.4 >= len(verse.text_am)
    await pilot.press('?')
    clock[0] += 2
    view.tick()
    await pilot.press('escape')
    await pilot.pause()
    assert FIXTURE in view.query_one('#verse-1').content.plain and not view.active


async def test_real_interval_completes_in_about_one_second(running_app, monkeypatch):
    app, pilot = running_app
    view = app.reader.query_one(VerseView)

    async def fake(service, ref):
        return FIXTURE

    monkeypatch.setattr('ebible.app.TranslationService.translate_verse', fake)
    completed = []
    original = VerseLine.update

    def track(widget, text):
        if widget.id == 'verse-1' and FIXTURE in text.plain:
            completed.append(monotonic())
        return original(widget, text)

    monkeypatch.setattr(VerseLine, 'update', track)
    await pilot.press('enter')
    await app.workers.wait_for_complete()
    state = view.morphs[VerseRef(1)]
    assert view.motion_timer._interval == FRAME_INTERVAL
    await pilot.pause(1.1)
    assert completed and 0.95 <= completed[0] - state.started <= 1.4
    assert not view.active and FIXTURE in view.query_one('#verse-1').content.plain
