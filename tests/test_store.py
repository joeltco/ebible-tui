"""Store and canon tests, run against the real compiled database."""

from __future__ import annotations

import pytest

from ebible import canon
from ebible.data.store import Store


@pytest.fixture(scope='module')
def store() -> Store:
    s = Store()
    yield s
    s.close()


# ------------------------------------------------------------------ canon


def test_canon_has_81_books() -> None:
    assert len(canon.BOOKS) == 81


def test_canon_ids_are_contiguous() -> None:
    assert [b.id for b in canon.BOOKS] == list(range(1, 82))


def test_canon_slugs_unique() -> None:
    slugs = [b.slug for b in canon.BOOKS]
    assert len(set(slugs)) == len(slugs)


def test_canon_matches_database(store: Store) -> None:
    """The shipped db must agree with the canon module it was built from."""
    assert {b.id for b in store.books} == {b.id for b in canon.BOOKS}
    for book in store.books:
        assert book.name_am == canon.by_id(book.id).name_am


# ------------------------------------------------------------------ totals


def test_totals(store: Store) -> None:
    st = store.stats()
    assert st.books == 81
    assert st.chapters == 1466
    assert st.verses == 39169


@pytest.mark.parametrize(
    ('slug', 'chapters'),
    [('genesis', 50), ('isaiah', 66), ('matthew', 28), ('jude', 1), ('revelation', 22)],
)
def test_known_chapter_counts(store: Store, slug: str, chapters: int) -> None:
    assert store.book_by_slug(slug).chapter_count == chapters


def test_every_chapter_has_verses(store: Store) -> None:
    """No chapter may be empty -- an empty one means the build dropped content."""
    empty = [
        (b.name_en, c)
        for b in store.books
        for c in range(1, b.chapter_count + 1)
        if not store.chapter(b.id, c)
    ]
    assert empty == []


def test_verse_numbers_start_at_one(store: Store) -> None:
    for slug in ('genesis', 'john', 'revelation'):
        book = store.book_by_slug(slug)
        assert store.chapter(book.id, 1)[0].verse == 1


# ------------------------------------------------------------------ navigation


def test_next_rolls_into_following_book(store: Store) -> None:
    assert store.next_chapter(1, 50) == (2, 1)


def test_prev_rolls_into_preceding_book(store: Store) -> None:
    assert store.prev_chapter(2, 1) == (1, 50)


def test_navigation_stops_at_canon_edges(store: Store) -> None:
    assert store.prev_chapter(1, 1) is None
    last = store.book(81)
    assert store.next_chapter(81, last.chapter_count) is None


def test_navigation_walks_whole_canon(store: Store) -> None:
    """Stepping forward from Genesis 1 must reach every chapter exactly once."""
    seen = 0
    pos: tuple[int, int] | None = (1, 1)
    while pos is not None:
        seen += 1
        pos = store.next_chapter(*pos)
    assert seen == 1466


# ------------------------------------------------------------------ search


def test_search_finds_amharic(store: Store) -> None:
    hits = store.search('እግዚአብሔር', limit=5)
    assert hits
    assert all(h.chapter >= 1 for h in hits)


def test_search_empty_query_returns_nothing(store: Store) -> None:
    assert store.search('   ') == []


def test_search_snippet_uses_guillemets_not_brackets(store: Store) -> None:
    """Brackets would be parsed as Rich markup and silently eat text."""
    hits = store.search('እግዚአብሔር', limit=1)
    assert '«' in hits[0].snippet
    assert '[' not in hits[0].snippet


# ------------------------------------------------------------------ translation state


def test_untranslated_is_none_not_empty_string(store: Store) -> None:
    """NULL means 'pending'; '' would mean a translation produced nothing."""
    verse = store.chapter(1, 1)[0]
    if not verse.translated:
        assert verse.text_en is None
