"""Focused regressions for the eight Batch 4 review items."""

import pytest
from textual.widgets import OptionList, Static

from ebible.core.models import VerseRef


@pytest.mark.parametrize(
    'singular,plural',
    [
        ('bookmark', 'bookmarks'),
        ('highlight', 'highlights'),
        ('note', 'notes'),
        ('history entry', 'history entries'),
        ('verse', 'verses'),
        ('passage', 'passages'),
        ('chapter', 'chapters'),
    ],
)
def test_count_labels_zero_one_many(singular, plural):
    from ebible.core.labels import count_label

    for n in (0, 1, 2):
        assert count_label(n, singular, plural) == f'{n} {singular if n == 1 else plural}'


async def test_collection_singular_plural_and_single_chapter_book(running_app):
    app, pilot = running_app
    ref = VerseRef(1)
    app.userdata.add_bookmark(ref)
    app.userdata.set_highlight(ref, 'gold')
    app.userdata.save_note(ref, app.scripture.verse(ref).text_am)  # Temporary real-text fixture.
    for kind, singular in [
        ('bookmarks', 'bookmark'),
        ('highlights', 'highlight'),
        ('notes', 'note'),
        ('history', 'history entry'),
    ]:
        await app.open_page(kind)
        await pilot.pause()
        assert str(app.screen.query_one('#collection-message', Static).content) == '1 ' + singular
        await pilot.press('escape')
    await pilot.press('b')
    app.screen.query_one('#book-filter').value = 'Obadiah'
    await pilot.pause()
    listing = app.screen.query_one(OptionList)
    assert '1 chapter' in listing.get_option_at_index(1).prompt.plain
    assert '1 chapters' not in listing.get_option_at_index(1).prompt.plain


async def test_plan_fractional_percent_is_never_zero_once_started(running_app):
    app, pilot = running_app
    await pilot.press('p')
    await app.screen.start()
    app.userdata.complete_day('canon-year', 1)
    await app.screen.reload()
    await pilot.pause()
    progress = app.screen.query_one('#plan-progress')
    label = progress.query_one('#percentage')
    assert label.render() == '<1%'
    for completed, expected in [(0, '0%'), (3, '<1%'), (4, '1%'), (365, '100%')]:
        progress.update(progress=completed)
        await pilot.pause()
        assert label.render() == expected


async def test_custom_themes_first_with_disabled_group_headings(running_app):
    from ebible.ui.themes import THEMES

    app, pilot = running_app
    custom = [t.name for t in THEMES]
    assert list(app.available_themes)[:6] == custom
    await pilot.press('s')
    choice = app.screen.query_one('#setting-theme')
    assert await pilot.click('#setting-theme SelectCurrent')
    await pilot.pause()
    listing = choice.query_one(OptionList)
    assert listing.get_option_at_index(0).prompt.plain == 'eBible themes'
    assert listing.get_option_at_index(0).disabled
    assert [value for _, value in choice._options[1:7]] == custom
    assert listing.get_option_at_index(7).prompt.plain == 'More themes'
    assert listing.get_option_at_index(7).disabled
    assert [value for _, value in choice._options[8:]] == list(app.available_themes)[6:]
    await pilot.press('up')  # Group title cannot be selected.
    assert not listing.get_option_at_index(listing.highlighted).disabled
    listing.highlighted = 1
    await pilot.press('down', 'enter')
    assert app.theme == 'tewahedo'


async def test_paragraph_resize_and_refresh_cannot_remove_each_others_blocks(running_app):
    import asyncio

    from ebible.ui.widgets.verse_view import Paragraph, VerseView

    app, pilot = running_app
    await app.update_setting('verse_flow', 'paragraph')
    view = app.reader.query_one(VerseView)
    await asyncio.gather(view.rebuild(), view.rebuild())
    await pilot.pause()
    assert len(view.query(Paragraph)) == 1
    assert app.reader.chapter_data.verses[0].text_am in view.query_one('#paragraph').content.plain


async def test_secondary_page_headers_one_row_and_resize(running_app):
    from textual.widgets import Button

    from ebible.ui.screens.books import ChaptersScreen
    from ebible.ui.screens.notes import NoteEditor

    app, pilot = running_app
    await pilot.resize_terminal(50, 30)
    for name in (
        'bookmarks',
        'books',
        'search',
        'settings',
        'plans',
        'notes',
        'help',
        'chapters',
        'editor',
    ):
        if name == 'chapters':
            await app.push_screen(ChaptersScreen(14))
        elif name == 'editor':
            await app.push_screen(NoteEditor(VerseRef(1)))
        else:
            await app.open_page(name)
        await pilot.pause()
        header = app.screen.query_one('.page-header')
        assert header.region.y == 0 and header.region.height == 1
        assert not app.screen.query_one('.heading-subtitle').display
        back = header.query_one(Button)
        assert back.region.height == 1 and back.region.width >= 3
        assert str(back.label) == '‹'
        assert await pilot.click(back)
        assert app.screen is app.reader
    await app.open_page('books')
    await pilot.resize_terminal(80, 40)
    await pilot.pause()
    header = app.screen.query_one('.page-header')
    assert header.region.height == 3 and header.region.y == 1
    assert app.screen.query_one('.heading-subtitle').display
    assert str(header.query_one(Button).label) == '‹ Back'


async def test_note_editor_copy_fits_one_line(running_app):
    from ebible.ui.screens.notes import NoteEditor

    app, pilot = running_app
    await app.push_screen(NoteEditor(VerseRef(1)))
    await pilot.pause()
    hint = next(w for w in app.screen.query(Static) if str(w.content).startswith('Markdown'))
    assert str(hint.content) == 'Markdown supported · saved only on this device'
    assert hint.region.height == 1


async def test_help_key_chips_have_fixed_accent_column_and_all_groups(running_app):
    from textual.color import Color

    app, pilot = running_app
    await pilot.press('?')
    await pilot.pause()
    help_card = app.screen.query_one('#help-text')
    headings = [str(w.content) for w in help_card.query('.eyebrow')]
    assert headings == [
        'READING',
        'FIND YOUR PLACE',
        'EVERYWHERE',
        'YOUR TEXT',
        'SEARCH',
        'THE ETHIOPIAN PSALTER',
    ]
    rows = list(help_card.query('.key-row'))
    assert len(rows) == 23
    for row in rows:
        chip = row.query_one('.key-chip')
        description = row.query_one('.key-description')
        assert chip.region.width == 16 and chip.region.height == 1
        assert chip.styles.color == Color.parse(app.get_css_variables()['accent'])
        assert description.region.x == chip.region.right + 1
        assert description.region.right < app.size.width
    assert {str(w.content) for w in help_card.query('.key-chip')} >= {
        'q',
        'Esc',
        'Tab',
        'Enter',
        'Enter / Space',
        'Backspace',
        'Delete',
    }
