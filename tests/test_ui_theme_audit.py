"""Actual SVG colours, all framework states, and live cache invalidation regressions."""

import runpy

import pytest
from textual.widgets import Button, Select

from ebible.app import EBibleApp
from ebible.core.models import HIGHLIGHT_COLOURS, VerseRef
from ebible.ui.morph import Morph
from ebible.ui.screens.search import QuerySummary
from ebible.ui.screens.title import Cover
from ebible.ui.themes import THEMES, highlight_colour
from ebible.ui.widgets.verse_view import VerseView

audit = runpy.run_path('tools/audit_themes.py')


@pytest.mark.parametrize('theme', THEMES, ids=lambda t: t.name)
async def test_rendered_roles_and_all_animation_frames(theme, tmp_path):
    report = await audit['probe'](tmp_path, (theme,))
    failures = []
    for capture in report:
        state = capture['state']
        animated = state.startswith(('forward', 'reverse', 'shimmer', 'query-shimmer', 'cover-'))
        for cell in capture['pairs']:
            role, char = cell['role'], cell['text']
            # Inactive content visible through a modal veil is deliberately unavailable.
            if role == 'VerseActions':
                continue
            # Identical-colour border filler is a blank, not visible text.
            if cell['fg'] == cell['bg']:
                continue
            decorative = not char.isalpha() or (role.startswith('verse-') and char.isdigit())
            threshold = 3 if animated or decorative else 4.5
            if theme.name == 'high-contrast' and role == 'verse-1' and animated:
                threshold = 7
            if cell['ratio'] < threshold:
                failures.append((state, cell, threshold))
    assert not failures, failures[:20]
    states = {c['state'] for c in report}
    assert {
        'input-selection',
        'input-cursor',
        'select-overlay',
        'toast-information',
        'toast-warning',
        'toast-error',
        'switch-modal-after',
        'switch-terms-after',
    } <= states
    for state, count in [
        ('forward', 40),
        ('reverse', 31),
        ('shimmer', 28),
        ('query-shimmer', 28),
        ('cover-entrance', 25),
        ('cover-opening', 18),
    ]:
        assert sum(c['state'] == state for c in report) == count

    def screenshot(state, frame=None):
        c = next(c for c in report if c['state'] == state and c['frame'] == frame)
        return audit['cells']((tmp_path / c['svg']).read_text(encoding='utf-8'))

    assert screenshot('query-final') == screenshot('query-reduced')
    assert screenshot('cover-entrance', 24) == screenshot('cover-reduced')
    assert screenshot('cover-open-final') == screenshot('reader-reduced')


@pytest.mark.parametrize('target', ['parchment', 'high-contrast', 'midnight'])
async def test_live_switch_mid_motion_settings_cover_search_and_modal(target):
    app = EBibleApp(reference=VerseRef(1), theme_name='meskel')
    async with app.run_test(size=(50, 30)) as pilot:
        await app.ready.wait()
        view = app.reader.query_one(VerseView)
        clock = [100.5]
        view.clock = lambda: clock[0]
        view.motion_timer.pause()
        ref = VerseRef(1)
        app.translations[ref] = 'Explicit temporary theme-switch fixture.'
        app.visible_translations.add(ref)
        view.morphs[ref] = Morph(0, 1, 100)
        view.update_verses({ref})
        before = view.body_text(app.scripture.verse(ref))
        await pilot.press('s')
        await pilot.pause()
        app.screen.query_one('#setting-theme', Select).value = target
        await pilot.pause()
        await pilot.press('escape')
        assert app.theme == target and view.morphs[ref].position(clock[0]) == 0.5
        assert view.body_text(app.scripture.verse(ref)) != before
        # A second direct switch must also invalidate Rich objects, including off-screen ones.
        await app.reader.action_verse_actions()
        for name in ('parchment', 'meskel', target):
            await app.update_setting('theme', name)
            await pilot.pause()
            rendered = audit['cells'](app.export_screenshot())
            for colour in HIGHLIGHT_COLOURS:
                button = app.screen.query_one('#highlight-' + colour, Button)
                dot = next(
                    cell
                    for cell in rendered
                    if cell['text'] == '●' and button.region.contains(cell['x'], cell['y'])
                )
                assert dot['fg'] == highlight_colour(colour, app.current_theme.dark)
        await pilot.press('escape')
        await app.open_page('search')
        await app.workers.wait_for_complete()
        summary = app.screen.query_one(QuerySummary)
        summary.show_terms('light', ('ብርሃን',))
        for name in ('meskel', target):
            await app.update_setting('theme', name)
            await pilot.pause()
            expected = app.get_css_variables()['accent']
            assert summary.content.spans[0].style.color.get_truecolor().hex == expected.lower()
        search = app.screen
        search.clock = lambda: clock[0]
        search.set_busy('fixture')
        search.busy_started = clock[0] - 0.45
        search.tick_busy()
        before = app.export_screenshot()
        await app.update_setting('theme', 'parchment' if target != 'parchment' else 'meskel')
        await pilot.pause()
        assert app.export_screenshot() != before
        search.set_busy(None)
        await pilot.press('escape')
        await app.show_title()
        title = app.screen
        title.clock = lambda: clock[0]
        title.phase, title.started = 'entrance', clock[0] - 0.4
        title.motion_timer.pause()
        before = title.query_one(Cover).render()
        await app.update_setting('theme', target)
        await pilot.pause()
        assert title.query_one(Cover).render() != before
        assert title.phase == 'entrance'


async def test_fetch_completion_and_interrupted_flourish_carry_colours_without_a_jump(monkeypatch):
    import asyncio

    app = EBibleApp(reference=VerseRef(1), theme_name='parchment')
    async with app.run_test(size=(50, 30)) as pilot:
        await app.ready.wait()
        view = app.reader.query_one(VerseView)
        clock = [100.0]
        view.clock = lambda: clock[0]
        view.motion_timer.pause()
        monkeypatch.setattr(view, '_wake_timer', lambda: None)
        release = asyncio.Event()

        async def fixture(service, ref):
            await release.wait()
            return 'Explicit temporary colour-continuity fixture.'

        monkeypatch.setattr('ebible.app.TranslationService.translate_verse', fixture)
        verse = app.scripture.verse(VerseRef(1))

        def styles():
            text = view.body_text(verse)
            return [
                (
                    text.get_style_at_offset(app.console, i).color,
                    text.get_style_at_offset(app.console, i).bgcolor,
                )
                for i in range(len(text))
            ]

        await pilot.press('enter')
        clock[0] += 0.45
        view.tick()
        pending = styles()
        release.set()
        await app.workers.wait_for_complete()
        assert styles() == pending
        clock[0] += 1.15
        view.tick()
        peak = styles()
        await pilot.press('enter')
        assert styles() == peak
        clock[0] += 1
        view.tick()
        assert not view.active
        assert view.body_text(verse).plain == verse.text_am
