"""Deterministic plans generated from the bundled canon's chapter counts."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from ebible.canon import BOOKS, Section
from ebible.core.models import PlanProgress

ChapterPosition = tuple[int, int]


@dataclass(frozen=True, slots=True)
class ReadingPlan:
    id: str
    name: str
    schedule: tuple[tuple[ChapterPosition, ...], ...]

    @property
    def days(self) -> int:
        return len(self.schedule)

    def day(self, number: int) -> tuple[ChapterPosition, ...]:
        if not 1 <= number <= self.days:
            raise ValueError(f'Day must be between 1 and {self.days}')
        return self.schedule[number - 1]

    def today(self, start: date, on: date | None = None) -> int | None:
        number = ((on or date.today()) - start).days + 1
        return number if 1 <= number <= self.days else None

    def progress(self, state: PlanProgress) -> float:
        if state.plan_id != self.id:
            raise ValueError('Progress belongs to another plan')
        return len({d for d in state.completed_days if 1 <= d <= self.days}) / self.days


def generate_plans(counts: Mapping[int, int]) -> tuple[ReadingPlan, ...]:
    if set(counts) != {b.id for b in BOOKS} or any(
        type(n) is not int or n < 1 for n in counts.values()
    ):
        raise ValueError('Positive chapter counts for all 81 books are required')
    definitions = (
        ('canon-year', 'Whole canon in a year', 365, {b.id for b in BOOKS}),
        ('nt-90', 'New Testament in 90 days', 90, {b.id for b in BOOKS if b.id >= 55}),
        ('wisdom-month', 'Psalms and Proverbs in 30 days', 30, {28, 29}),
        (
            'gospels-30',
            'Gospels in 30 days',
            30,
            {b.id for b in BOOKS if b.section == Section.GOSPELS},
        ),
    )
    plans: list[ReadingPlan] = []
    for plan_id, name, days, books in definitions:
        chapters = [(b.id, c) for b in BOOKS if b.id in books for c in range(1, counts[b.id] + 1)]
        # Contiguous, balanced groups in Ethiopian order, no omissions/repeats.
        base, extra = divmod(len(chapters), days)
        schedule: list[tuple[ChapterPosition, ...]] = []
        cursor = 0
        for index in range(days):
            size = base + (index < extra)
            schedule.append(tuple(chapters[cursor : cursor + size]))
            cursor += size
        plans.append(ReadingPlan(plan_id, name, tuple(schedule)))
    return tuple(plans)


def current_streak(state: PlanProgress, on: date | None = None) -> int:
    """Consecutive calendar days with completions; yesterday keeps a streak alive."""
    day = on or date.today()
    if day not in state.completed_dates:
        day -= timedelta(days=1)
    count = 0
    while day in state.completed_dates:
        count += 1
        day -= timedelta(days=1)
    return count
