"""Focused regressions for the Batch 4 search, count, and progress fixes."""

from xml.etree import ElementTree as ET

import pytest
from textual.widgets import OptionList, Static

from ebible.core.models import VerseRef


def test_real_amos_snippet_preserves_every_character(scripture):
    from ebible.ui.screens.search import snippet_text

    ref = VerseRef(44, 7, 6)
    result = next(r for r in scripture.search('LORD') if r.ref == ref)
    plain = result.snippet.replace('\x01', '').replace('\x02', '')
    rendered = snippet_text(result.snippet)
    assert rendered.plain == plain == scripture.verse(ref).english
    assert 'LORD repented' in rendered.plain
    # Explicit whitespace fixture: only control markers may disappear.
    assert snippet_text(' \t\x01LORD\x02  \n repented ').plain == ' \tLORD  \n repented '


async def test_real_amos_search_export_keeps_gap_after_highlight(running_app):
    app, pilot = running_app
    await pilot.press('/')
    app.screen.query_one('#search-input').value = 'LORD'
    await pilot.pause()
    await app.workers.wait_for_complete()
    listing = app.screen.query_one('#search-results', OptionList)
    index = next(i for i, r in enumerate(app.screen.results) if r.ref == VerseRef(44, 7, 6))
    prompt = listing.get_option_at_index(index).prompt
    assert 'LORD repented' in prompt.plain
    listing.highlighted = index
    listing.scroll_to_highlight()
    await pilot.pause()
    nodes = list(ET.fromstring(app.export_screenshot()).iter('{http://www.w3.org/2000/svg}text'))
    following = next(n for n in nodes if (n.text or '').startswith('repented'))
    preceding = next(n for n in nodes if n.text == 'LORD' and n.get('y') == following.get('y'))
    cell = float(preceding.get('textLength')) / 4
    assert float(following.get('x')) >= float(preceding.get('x')) + 5 * cell - 0.01


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
    app.userdata.save_note(ref, app.scripture.verse(ref).english)  # Temporary real-text fixture.
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
