import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date, timedelta

import pytest

from ebible.canon import BOOKS, Section
from ebible.core.models import VerseRef
from ebible.core.plans import current_streak, generate_plans
from ebible.core.userdata import _MIGRATIONS, SCHEMA_VERSION, UserDataStore


def test_migrations_empty_and_reopen(userdata):
    with closing(sqlite3.connect(userdata.path)) as db, db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == SCHEMA_VERSION
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        'bookmark',
        'highlight',
        'note',
        'history',
        'reading_position',
        'plan',
        'plan_progress',
    } <= tables
    assert 'live_translation' not in tables
    userdata.add_bookmark(VerseRef(1))
    assert UserDataStore(userdata.path).bookmarks() == userdata.bookmarks()


def test_forward_migration_preserves_data(tmp_path):
    path = tmp_path / 'fixture-v1.db'
    with closing(sqlite3.connect(path)) as db, db:
        for statement in _MIGRATIONS[1]:
            db.execute(statement)
        db.execute('PRAGMA user_version=1')
        db.execute("INSERT INTO bookmark VALUES(1,1,1,'2026-01-01T00:00:00+00:00')")
    store = UserDataStore(path)
    assert store.bookmarks()[0].ref == VerseRef(1)
    assert not hasattr(store, 'live_chapter')


def test_future_version_rejected_unchanged(tmp_path):
    path = tmp_path / 'fixture-future.db'
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('PRAGMA user_version=999')
    with pytest.raises(ValueError, match='newer'):
        UserDataStore(path)
    with closing(sqlite3.connect(path)) as db, db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 999
        assert db.execute('SELECT count(*) FROM sqlite_master').fetchone()[0] == 0


def test_v2_cache_dropped_and_personal_data_survives(userdata, scripture):
    ref = VerseRef(1)
    userdata.add_bookmark(ref)
    userdata.set_highlight(ref, 'gold')
    userdata.save_note(ref, 'Explicit temporary note fixture')
    userdata.record_position(ref)
    plan = generate_plans(scripture.chapter_counts())[0]
    userdata.start_plan(plan, date.today())
    userdata.complete_day(plan.id, 1)
    before = (
        userdata.bookmarks(),
        userdata.highlights(),
        userdata.notes(),
        userdata.history(),
        userdata.reading_position(),
        userdata.plan_progress(plan.id),
    )
    sentinel = 'Explicit legacy translation fixture to erase'
    with sqlite3.connect(userdata.path) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('DROP TABLE IF EXISTS live_translation')
        db.execute(_MIGRATIONS[2][0])
        db.execute(
            'INSERT INTO live_translation VALUES(1,1,1,?,?,?)',
            (sentinel, 'fixture', '2026-01-01T00:00:00+00:00'),
        )
        db.execute('PRAGMA user_version=2')
    migrated = UserDataStore(userdata.path)
    assert before == (
        migrated.bookmarks(),
        migrated.highlights(),
        migrated.notes(),
        migrated.history(),
        migrated.reading_position(),
        migrated.plan_progress(plan.id),
    )
    with sqlite3.connect(userdata.path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 3
        assert not db.execute(
            "SELECT name FROM sqlite_master WHERE name='live_translation'"
        ).fetchall()
    for file in userdata.path.parent.iterdir():
        assert sentinel.encode() not in file.read_bytes()
    for method in ('save_translations', 'live_chapter', 'live_translation', 'delete_translation'):
        assert not hasattr(migrated, method)


def test_migration_failure_rolls_back(tmp_path, monkeypatch):
    monkeypatch.setitem(_MIGRATIONS, 2, ('INVALID SQL',))
    path = tmp_path / 'fixture-failure.db'
    with pytest.raises(sqlite3.OperationalError):
        UserDataStore(path)
    with closing(sqlite3.connect(path)) as db, db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM sqlite_master').fetchone()[0] == 0


def test_annotations_roundtrip_update_delete(userdata):
    ref = VerseRef(58, 3, 16)
    userdata.add_bookmark(ref)
    userdata.add_bookmark(ref)
    assert len(userdata.bookmarks()) == 1
    assert userdata.bookmarks()[0].created_at.tzinfo is not None
    userdata.set_highlight(ref, 'gold')
    created = userdata.highlights()[0].created_at
    userdata.set_highlight(ref, 'blue')
    assert userdata.highlights()[0].colour == 'blue'
    assert userdata.highlights()[0].created_at == created
    # Explicit temporary note fixtures; these are not scripture or sample app data.
    userdata.save_note(ref, 'fixture: **markdown** [link] አማርኛ')
    first = userdata.notes()[0]
    userdata.save_note(ref, 'fixture: edited note')
    note = userdata.notes()[0]
    assert note.created_at == first.created_at
    assert note.updated_at >= first.updated_at
    assert note.text == 'fixture: edited note'
    assert UserDataStore(userdata.path).notes() == userdata.notes()
    userdata.delete_bookmark(ref)
    userdata.delete_highlight(ref)
    userdata.delete_note(ref)
    assert userdata.bookmarks() == userdata.highlights() == userdata.notes() == ()
    with pytest.raises(ValueError):
        userdata.set_highlight(ref, 'invisible')
    with pytest.raises(ValueError):
        userdata.add_bookmark(VerseRef(1, 1, 1, 2))


def test_resume_history_pruned_and_deduplicated(tmp_path):
    store = UserDataStore(tmp_path / 'fixture.db', history_limit=2)
    assert store.reading_position() is None
    for verse in (1, 2, 2, 3):
        store.record_position(VerseRef(1, 1, verse))
    assert [h.ref.verse for h in store.history()] == [3, 2]
    assert UserDataStore(store.path).reading_position() == VerseRef(1, 1, 3)
    store.delete_history(store.history()[0].id)
    assert [h.ref.verse for h in store.history()] == [2]
    assert store.reading_position() == VerseRef(1, 1, 3)
    with pytest.raises(ValueError):
        UserDataStore(tmp_path / 'invalid.db', history_limit=0)


def test_userdata_worker_connections(userdata):
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(lambda v: userdata.add_bookmark(VerseRef(1, 1, v)), range(1, 9)))
    assert len(userdata.bookmarks()) == 8


def test_all_generated_plans_exact_coverage(scripture):
    counts = scripture.chapter_counts()
    plans = generate_plans(counts)
    assert [p.days for p in plans] == [365, 90, 30, 30]
    selections = [
        BOOKS,
        [b for b in BOOKS if b.id >= 55],
        [b for b in BOOKS if b.id in (28, 29)],
        [b for b in BOOKS if b.section == Section.GOSPELS],
    ]
    for plan, books in zip(plans, selections, strict=True):
        expected = [(b.id, c) for b in books for c in range(1, counts[b.id] + 1)]
        chapters = [c for day in range(1, plan.days + 1) for c in plan.day(day)]
        assert chapters == expected
        assert len(set(chapters)) == len(chapters)
        assert max(map(len, plan.schedule)) - min(map(len, plan.schedule)) <= 1
        assert all(plan.schedule)
        for number in (0, plan.days + 1):
            with pytest.raises(ValueError):
                plan.day(number)
    for counts_bad in ({}, {**counts, 1: 0}, {**counts, 1: True}):
        with pytest.raises(ValueError):
            generate_plans(counts_bad)


def test_today_progress_streak_restart(userdata, scripture):
    plan = generate_plans(scripture.chapter_counts())[0]
    start = date(2026, 1, 1)
    assert plan.today(start, start) == 1
    assert plan.today(start, start - timedelta(days=1)) is None
    assert plan.today(start, start + timedelta(days=364)) == 365
    assert plan.today(start, start + timedelta(days=365)) is None
    assert plan.today(date.today()) == 1
    assert userdata.plan_progress(plan.id) is None
    userdata.start_plan(plan, start)
    assert plan.progress(userdata.plan_progress(plan.id)) == 0
    for day in (1, 2, 3):
        userdata.complete_day(plan.id, day, on=start + timedelta(days=day - 1))
    userdata.complete_day(plan.id, 3, on=start + timedelta(days=4))
    state = userdata.plan_progress(plan.id)
    assert state.completed_days == frozenset({1, 2, 3})
    assert plan.progress(state) == 3 / 365
    assert current_streak(state, start + timedelta(days=2)) == 3
    assert current_streak(state, start + timedelta(days=3)) == 3
    assert current_streak(state, start + timedelta(days=4)) == 0
    assert current_streak(state) == 0
    with pytest.raises(ValueError):
        generate_plans(scripture.chapter_counts())[1].progress(state)
    for day in (0, 366):
        with pytest.raises(ValueError):
            userdata.complete_day(plan.id, day, on=start)
    with pytest.raises(ValueError):
        userdata.complete_day('unknown', 1)
    with pytest.raises(ValueError):
        userdata.complete_day(plan.id, 1, on=start - timedelta(days=1))
    userdata.uncomplete_day(plan.id, 2)
    assert current_streak(userdata.plan_progress(plan.id), start + timedelta(days=2)) == 1
    userdata.start_plan(plan, date.today())
    assert not userdata.plan_progress(plan.id).completed_days
    userdata.complete_day(plan.id, 1)
    assert current_streak(userdata.plan_progress(plan.id)) == 1
