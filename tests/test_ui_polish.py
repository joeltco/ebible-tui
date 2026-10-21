"""Batch 3 regressions: actual mounted geometry and visible reading content."""

import pytest
from rich.text import Text
from textual.widgets import Button, Static

from ebible.canon import BOOKS, BY_ID
from ebible.core.models import VerseRef
from ebible.ui.widgets.header import HeaderBar
from ebible.ui.widgets.verse_view import Paragraph, VerseLine, VerseView


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


@pytest.mark.parametrize('flow', ['lines', 'paragraph'])
async def test_untranslated_chapter_has_one_notice_and_amharic_only(running_app, flow):
    app, pilot = running_app
    await app.navigate(VerseRef(15))  # Real Jubilees chapter with no bundled English.
    await app.update_setting('verse_flow', flow)
    for layout in ('amharic', 'english', 'interleaved', 'parallel'):
        await app.update_setting('layout', layout)
        await pilot.pause()
        view = app.reader.query_one(VerseView)
        notice = view.query_one('#chapter-notice', Static)
        assert len(view.query('#chapter-notice')) == 1
        text = str(notice.content)
        assert 'deuterocanonical' in text and 'not yet translated' in text
        assert 'Translate this chapter' in text and 'verse menu' in text and 'backend' in text
        assert '◇' not in text
        assert view.effective_layout == 'amharic'
        assert notice.region.y >= app.reader.query_one('#reading-scroll').content_region.y
        assert app.reader.query_one('#reading-scroll').scroll_y == 0
        if flow == 'lines':
            rendered = '\n'.join(line.content.plain for line in view.query(VerseLine))
        else:
            rendered = view.query_one(Paragraph).content.plain
        assert 'translated' not in rendered and '◇' not in rendered
        assert app.reader.chapter_data.verses[0].text_am in rendered
        assert app.reader.chapter_data.verses[-1].text_am in rendered
    await app.navigate(VerseRef(1))
    assert not view.query('#chapter-notice')
    await pilot.press('enter')
    assert '◇' not in str(app.screen.query_one('#bookmark-verse', Button).label)


@pytest.mark.parametrize('flow', ['lines', 'paragraph'])
async def test_partial_translation_uses_short_placeholder_and_exclusive_machine_marker(
    running_app, flow
):
    app, pilot = running_app
    # Explicit temporary overlay fixture; content is real bundled English, not a translation.
    real = app.scripture.verse(VerseRef(1)).english
    app.userdata.save_translations(15, 1, {1: real}, 'fixture')
    await app.navigate(VerseRef(15))
    await app.update_setting('verse_flow', flow)
    await pilot.pause()
    view = app.reader.query_one(VerseView)
    assert not view.query('#chapter-notice')
    if flow == 'lines':
        rendered = '\n'.join(line.content.plain for line in view.query(VerseLine))
    else:
        rendered = view.query_one(Paragraph).content.plain
    assert rendered.count('◇') == 1
    assert '◇ Machine' in rendered and real in rendered
    assert 'Not yet translated' in rendered
    assert 'no bundled English' not in rendered and 'deuterocanonical' not in rendered
    missing = view.verse_text(app.reader.chapter_data.verses[1], 'en', gutter=False)
    assert len(missing.plain) <= 20
    assert missing.spans and any(span.style.italic for span in missing.spans)
    await app.update_setting('show_untranslated_placeholder', False)
    assert (
        view.verse_text(app.reader.chapter_data.verses[1], 'en', gutter=False).plain
        == 'Untranslated'
    )


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

    for key in (None, 'b', '/', 'm', 'v', 'n', 't', 'p', 's', '?', 'g', 'enter'):
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
