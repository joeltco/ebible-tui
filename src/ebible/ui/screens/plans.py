"""Generated reading plans with today's chapters, calendar streaks, and progress."""

import asyncio
from datetime import date

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, OptionList, ProgressBar, Select, Static
from textual.widgets._progress_bar import Bar, PercentageStatus
from textual.widgets.option_list import Option

from ebible.core.models import PlanProgress, VerseRef
from ebible.core.plans import ReadingPlan, current_streak, generate_plans
from ebible.core.refs import format_reference
from ebible.ui.screens.base import Confirm, Page
from ebible.ui.widgets.controls import Choice, PassageList, PhoneScroll


class PlanPercentage(PercentageStatus):
    def render(self) -> str:
        progress = self.parent
        if isinstance(progress, ProgressBar):
            fraction = progress.percentage
            if fraction is not None and 0 < fraction < 0.01:
                return '<1%'
        return str(super().render())


class PlanProgressBar(ProgressBar):
    def compose(self) -> ComposeResult:
        yield Bar(id='bar').data_bind(ProgressBar.percentage)
        yield PlanPercentage(id='percentage').data_bind(ProgressBar.percentage)


class PlansScreen(Page):
    def __init__(self) -> None:
        super().__init__()
        self.plans: dict[str, ReadingPlan] = {}
        self.plan_id = 'canon-year'
        self.view_day = 1
        self.progress: PlanProgress | None = None
        self._initializing = True

    @property
    def plan(self) -> ReadingPlan:
        return self.plans[self.plan_id]

    def compose(self) -> ComposeResult:
        self.plans = {plan.id: plan for plan in generate_plans(self.eb.chapter_counts)}
        yield from self.heading(
            'A little, every day', 'Read at your own pace · return where you left off'
        )
        yield Choice(
            [(p.name, p.id) for p in self.plans.values()],
            value=self.plan_id,
            allow_blank=False,
            id='plan-choice',
        )
        with PhoneScroll(classes='page-scroll', id='plan-scroll'):
            yield Static('', id='plan-summary', classes='page-subtitle', markup=False)
            yield PlanProgressBar(total=self.plan.days, show_eta=False, id='plan-progress')
            with Horizontal(classes='button-row'):
                yield Button('‹ Day', id='previous-day')
                yield Button('Today', id='today-day')
                yield Button('Day ›', id='next-day')
            yield Static('', id='plan-day', classes='eyebrow', markup=False)
            yield PassageList(id='plan-readings')
            yield Button('Start today', id='start-plan', variant='primary')
            yield Button('Mark day read', id='mark-read', disabled=True)

    async def on_mount(self) -> None:
        await self.reload(reset_day=True)
        self._initializing = False

    async def reload(self, *, reset_day: bool = False) -> None:
        self.progress = await asyncio.to_thread(self.eb.userdata.plan_progress, self.plan_id)
        state = self.progress
        today = self.plan.today(state.start_date) if state else None
        if reset_day:
            self.view_day = today or 1
        completed = len(state.completed_days) if state else 0
        streak = current_streak(state) if state else 0
        self.query_one('#plan-summary', Static).update(
            f'{completed} / {self.plan.days} days read · {streak}-day streak\n'
            + (
                f'Started {state.start_date:%d %b %Y}'
                if state
                else 'Start today to keep your progress on this device.'
            )
        )
        self.query_one(ProgressBar).update(total=self.plan.days, progress=completed)
        done = state is not None and self.view_day in state.completed_days
        self.query_one('#plan-day', Static).update(
            f'DAY {self.view_day} / {self.plan.days}'
            + (' · TODAY' if today == self.view_day else '')
            + (' · READ ✓' if done else '')
        )
        options = []
        for index, (book, chapter) in enumerate(self.plan.day(self.view_day)):
            text = Text(format_reference(VerseRef(book, chapter)).rsplit(':', 1)[0])
            options.append(Option(text, id=f'plan-reading-{index}'))
        self.query_one('#plan-readings', OptionList).clear_options().add_options(options)
        self.query_one('#plan-readings', OptionList).highlighted = 0 if options else None
        self.query_one('#start-plan', Button).label = (
            'Restart from today' if state else 'Start today'
        )
        mark = self.query_one('#mark-read', Button)
        mark.disabled = state is None or (state is not None and date.today() < state.start_date)
        mark.label = 'Mark unread' if done else 'Mark day read'
        self.query_one('#previous-day', Button).disabled = self.view_day == 1
        self.query_one('#next-day', Button).disabled = self.view_day == self.plan.days
        self.query_one('#today-day', Button).disabled = today is None

    async def on_select_changed(self, event: Select.Changed) -> None:
        if not self._initializing and isinstance(event.value, str):
            self.plan_id = event.value
            await self.reload(reset_day=True)

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            index = int(event.option_id.removeprefix('plan-reading-'))
            book, chapter = self.plan.day(self.view_day)[index]
            await self.eb.navigate(VerseRef(book, chapter))

    async def start(self) -> None:
        await asyncio.to_thread(self.eb.userdata.start_plan, self.plan, date.today())
        await self.reload(reset_day=True)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        name = event.button.id
        if name == 'start-plan':
            event.stop()
            if self.progress:
                await self.app.push_screen(
                    Confirm('Restart this plan and clear its completed days?', self.start)
                )
            else:
                await self.start()
        elif name == 'mark-read':
            event.stop()
            if self.progress:
                done = self.view_day in self.progress.completed_days
                await asyncio.to_thread(
                    self.eb.userdata.uncomplete_day if done else self.eb.userdata.complete_day,
                    self.plan_id,
                    self.view_day,
                )
                await self.reload()
        elif name in ('previous-day', 'next-day', 'today-day'):
            event.stop()
            if name == 'today-day' and self.progress:
                self.view_day = self.plan.today(self.progress.start_date) or self.view_day
            else:
                self.view_day = max(
                    1, min(self.plan.days, self.view_day + (-1 if name == 'previous-day' else 1))
                )
            await self.reload()
        else:
            await super().on_button_pressed(event)
