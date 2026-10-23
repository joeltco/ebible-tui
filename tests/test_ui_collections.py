import asyncio

from textual.widgets import Button, OptionList, Static

from ebible.app import EBibleApp
from ebible.core.models import VerseRef
from ebible.ui.screens.base import Confirm
from ebible.ui.screens.notes import NoteEditor
from ebible.ui.screens.verse_actions import VerseActions
from ebible.ui.widgets.controls import NoteArea
from ebible.ui.widgets.verse_view import VerseView


async def test_annotation_roundtrip_restart_and_confirmed_deletion(terminal_size):
    app = EBibleApp(VerseRef(58, 3, 16))
    # Explicit note fixture in the isolated XDG temporary directory.
    fixture_note = '**Temporary test fixture**\nA note with [literal brackets] and አማርኛ.'
    async with app.run_test(size=terminal_size) as pilot:
        await asyncio.wait_for(app.ready.wait(), 5)
        await pilot.press('a')
        await pilot.click('#bookmark-verse')
        assert app.userdata.bookmarks()[0].ref == VerseRef(58, 3, 16)
        assert 'Bookmarked' in str(app.screen.query_one('#bookmark-verse', Button).label)
        await pilot.click('#highlight-gold')
        assert app.userdata.highlights()[0].colour == 'gold'
        await pilot.click('#note-verse')
        assert isinstance(app.screen, NoteEditor)
        app.screen.query_one(NoteArea).load_text(fixture_note)
        await pilot.click('#save-note')
        assert isinstance(app.screen, VerseActions)
        assert app.userdata.notes()[0].text == fixture_note
        await pilot.press('escape')
        view = app.reader.query_one(VerseView)
        assert 16 in view.bookmarks and 16 in view.notes
        assert view.highlights[16] == 'gold'
        verse = app.scripture.verse(VerseRef(58, 3, 16))
        assert '◆✎' in view.verse_text(verse).plain
    restarted = EBibleApp()
    async with restarted.run_test(size=terminal_size) as pilot:
        await asyncio.wait_for(restarted.ready.wait(), 5)
        assert restarted.reference == VerseRef(58, 3, 16)
        view = restarted.reader.query_one(VerseView)
        assert 16 in view.bookmarks and 16 in view.notes and view.highlights[16] == 'gold'
        await pilot.press('n')
        assert fixture_note.replace('\n', ' ') in str(
            restarted.screen.query_one(OptionList).get_option_at_index(0).prompt
        )
        await pilot.click('#edit-entry')
        assert restarted.screen.query_one(NoteArea).text == fixture_note
        restarted.screen.query_one(NoteArea).load_text(fixture_note + '\nEdited fixture.')
        await pilot.click('#save-note')
        await pilot.pause()
        assert restarted.userdata.notes()[0].text.endswith('Edited fixture.')
        for tab, getter in [
            ('notes', restarted.userdata.notes),
            ('highlights', restarted.userdata.highlights),
            ('bookmarks', restarted.userdata.bookmarks),
        ]:
            await pilot.click(f'#tab-{tab}')
            await pilot.pause()
            await pilot.click('#delete-entry')
            assert isinstance(restarted.screen, Confirm)
            await pilot.click('#cancel')
            assert getter()
            await pilot.click('#delete-entry')
            await pilot.click('#confirm')
            await pilot.pause()
            assert not getter()
            assert 'No ' in str(restarted.screen.query_one('#collection-message', Static).content)
        await pilot.press('escape')
        assert 16 not in view.bookmarks and 16 not in view.notes and 16 not in view.highlights


async def test_note_escape_discard_and_literal_typing(running_app):
    app, pilot = running_app
    await pilot.press('a')
    await pilot.click('#note-verse')
    await pilot.press('q', 'j', 's', 'n')
    assert app.screen.query_one(NoteArea).text == 'qjsn'
    assert not app._exit
    await pilot.press('escape')
    assert isinstance(app.screen, Confirm)
    await pilot.press('escape')
    assert isinstance(app.screen, NoteEditor)
    assert app.screen.query_one(NoteArea).text == 'qjsn'
    await pilot.press('escape')
    await pilot.click('#confirm')
    assert isinstance(app.screen, VerseActions)
    assert not app.userdata.notes()
    await pilot.click('#note-verse')
    await pilot.press('escape')
    assert isinstance(app.screen, VerseActions)


async def test_toggle_bookmark_clear_highlight_and_collection_jump(running_app):
    app, pilot = running_app
    await app.navigate(VerseRef(58, 3, 16))
    await pilot.press('a')
    await pilot.click('#bookmark-verse')
    await pilot.click('#bookmark-verse')
    assert not app.userdata.bookmarks()
    await pilot.click('#bookmark-verse')
    await pilot.click('#highlight-blue')
    assert app.userdata.highlights()[0].colour == 'blue'
    await pilot.click('#highlight-clear')
    assert not app.userdata.highlights()
    await pilot.press('escape')
    await app.navigate(VerseRef(1))
    await pilot.press('m')
    app.screen.query_one(OptionList).focus()
    await pilot.press('enter')
    assert app.reference == VerseRef(58, 3, 16)
    assert app.screen is app.reader


async def test_history_jump_delete_and_invalid_saved_reference(running_app):
    app, pilot = running_app
    await app.navigate(VerseRef(58, 3, 16))
    await app.navigate(VerseRef(1))
    await pilot.press('t')
    listing = app.screen.query_one(OptionList)
    listing.highlighted = 1
    listing.focus()
    await pilot.press('enter')
    assert app.reference == VerseRef(58, 3, 16)
    await pilot.press('t')
    count = len(app.userdata.history())
    await pilot.click('#delete-entry')
    await pilot.click('#confirm')
    assert len(app.userdata.history()) == count - 1
    assert app.userdata.reading_position() == VerseRef(58, 3, 16)
    await pilot.press('escape')
    # Explicit invalid stored fixture verifies all stored jumps use the same validator.
    app.userdata.add_bookmark(VerseRef(28, 151))
    await pilot.press('m')
    await pilot.click('#open-entry')
    assert app.screen.__class__.__name__ == 'BookmarksScreen'
    assert '150:7-14' in app.last_message
    assert app.reference == VerseRef(58, 3, 16)


async def test_note_undo_redo_and_tab_out_of_editor(running_app):
    app, pilot = running_app
    await pilot.press('a')
    await pilot.click('#note-verse')
    await pilot.press('a', 'b', 'c')  # Explicit temporary note fixture.
    editor = app.screen.query_one(NoteArea)
    assert editor.text == 'abc'
    await pilot.press('tab')
    assert app.focused is not editor
    await pilot.click('#undo-note')
    assert editor.text != 'abc'
    await pilot.click('#redo-note')
    assert editor.text == 'abc'
