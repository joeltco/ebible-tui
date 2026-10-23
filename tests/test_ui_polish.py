"""Batch 3 regressions: actual mounted geometry and visible reading content."""

from rich.text import Text
from textual.widgets import Button, Static

from ebible.canon import BOOKS, BY_ID
from ebible.core.models import VerseRef
from ebible.ui.widgets.header import HeaderBar


async def test_compact_header_row_budget_names_touch_and_resize(running_app):
    app, pilot = running_app
    await pilot.resize_terminal(50, 30)
    await pilot.pause()
    header = app.reader.query_one(HeaderBar)
    assert header.region.height == 1
    assert not app.reader.query_one('#brand').display
    viewport = app.reader.query_one('#reading-scroll')
    assert viewport.content_size.height >= 24
    assert viewport.styles.padding.top == viewport.styles.padding.bottom == 0
    for book in [BY_ID[14], *(b for b in BOOKS if 'Meqabyan' in b.name_en)]:
        await app.navigate(VerseRef(book.id))
        await pilot.pause()
        title = header.query_one('#book-title', Static)
        assert isinstance(title.content, Text)
        assert title.content.plain.endswith(f' 1/{app.chapter_counts[book.id]}')
        assert '\n' not in title.content.plain
        assert title.content.cell_len <= title.content_size.width
        for button in header.query(Button):
            assert button.region.height == 1 and button.region.width >= 3
            assert button.region.right <= app.size.width
    # Constrain the title to exercise ellipsis using a real, long book name.
    title.styles.width = 20
    await pilot.pause()
    header.show_title(BY_ID[14].display, 1, app.chapter_counts[14])
    assert '…' in title.content.plain
    assert title.content.plain.endswith(' 1/36')
    title.styles.width = '1fr'
    await app.navigate(VerseRef(1))
    assert await pilot.click('#next-chapter')
    await pilot.pause()
    assert app.reference == VerseRef(1, 2)
    assert await pilot.click('#previous-chapter')
    await pilot.pause()
    assert app.reference == VerseRef(1)
    await pilot.resize_terminal(80, 30)
    await pilot.pause()
    assert header.region.height == 3
    assert app.reader.query_one('#brand').display
    assert '\nCHAPTER 1' in header.query_one('#book-title', Static).content.plain
    await pilot.resize_terminal(79, 30)
    await pilot.pause()
    assert header.region.height == 1


async def test_plan_percentage_and_bar_stay_inside_column_with_gap(running_app):
    app, pilot = running_app
    await pilot.press('p')
    await pilot.pause()
    scroll = app.screen.query_one('#plan-scroll')
    progress = app.screen.query_one('#plan-progress')
    bar = progress.query_one('Bar')
    label = progress.query_one('PercentageStatus')
    for amount in (0, 1, 365):
        progress.update(progress=amount)
        await pilot.pause()
        assert label.region.x >= bar.region.right + 1
        assert label.region.right <= progress.content_region.right
        assert label.region.right < scroll.content_region.right
        if scroll.show_vertical_scrollbar:
            assert label.region.right <= scroll.vertical_scrollbar.region.x - 1
        assert label.region.y == bar.region.y
    assert '100%' in app.export_screenshot()


async def test_scrollbars_one_cell_visible_and_themed_throughout(running_app):
    app, pilot = running_app

    for key in (None, 'b', '/', 'm', 'v', 'n', 't', 'p', 's', '?', 'g', 'a'):
        if key:
            await pilot.press(key)
        await pilot.pause()
        seen = []
        for widget in app.screen.walk_children():
            if widget.is_scrollable:
                assert widget.styles.scrollbar_size_vertical == 1
                assert widget.styles.scrollbar_size_horizontal == 1
                if widget.show_vertical_scrollbar:
                    seen.append(widget)
                    assert widget.vertical_scrollbar.region.width == 1
                    assert widget.styles.scrollbar_color != widget.styles.scrollbar_background
        if key in (None, 'b', 's', '?'):
            assert seen
        if key:
            await pilot.press('escape')


async def test_theme_dropdown_shows_multiple_choices_and_accepts_taps(running_app):
    app, pilot = running_app
    await pilot.press('s')
    assert await pilot.click('#setting-theme SelectCurrent')
    await pilot.pause()
    choice = app.screen.query_one('#setting-theme')
    overlay = choice.query_one('SelectOverlay')
    assert overlay.content_size.height >= 4
    assert overlay.region.x == choice.region.x
    assert overlay.region.width == choice.region.width
    assert overlay.show_vertical_scrollbar
    assert overlay.vertical_scrollbar.region.width == 1
    overlay.scroll_home(animate=False)
    await pilot.pause()
    assert await pilot.click(overlay, offset=(3, 3))
    await pilot.pause()
    assert app.theme == list(app.available_themes)[1]
    assert not choice.expanded
