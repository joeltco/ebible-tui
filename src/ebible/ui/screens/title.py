"""A literal, cell-aligned frontispiece over the already prepared reader."""

from collections.abc import Callable
from time import monotonic

from rich.console import Console
from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widget import Widget

from ebible.core.models import VerseRef
from ebible.core.refs import format_reference
from ebible.ui.morph import FRAME_INTERVAL, Palette, palette
from ebible.ui.screens.base import Page
from ebible.ui.themes import effect_colours

ENTRANCE_DURATION = 0.8
OPEN_DURATION = 0.6
ORNAMENTS = '╔╗╚╝═║✦❖✣│─'
# The source numbers Psalms as the Ethiopian/Septuagint canon does; label it as the reader does.
EPIGRAPH = VerseRef(28, 118, 105)


def cover_art(
    width: int,
    height: int,
    progress: float,
    colours: Palette,
    epigraph: str,
    position: str,
    continuing: bool,
    selected: int,
) -> tuple[list[Text], list[tuple[int, int, int, int]]]:
    """Return exact-width lines and tap rectangles; no scripture is treated as markup."""
    background = colours.effects.panel
    base = Style(color=colours.ink.hex)
    lines = [Text(' ' * width, style=base, no_wrap=True) for _ in range(height)]
    left = max(1, (width - 66) // 2)
    right = width - left - 1
    top = max(1, (height - 32) // 2)
    bottom = height - top - 1
    for y in range(top, bottom + 1):
        lines[y].stylize(Style(bgcolor=background.hex), left, right + 1)
    inside = right - left - 5
    frame = colours.accent.hex
    fade = max(0.0, min(1.0, (progress - 0.45) / 0.55))
    title_ink = background.blend(colours.effects.glow, fade).hex
    quiet = Style(color=background.blend(colours.translation, fade).hex)

    def put(x: int, y: int, text: Text) -> None:
        if 0 <= y < height:
            text = text.copy()
            if top <= y <= bottom:
                text.stylize_before(Style(bgcolor=background.hex))
            text.truncate(max(0, width - x), overflow='ellipsis')
            lines[y] = lines[y][:x] + text + lines[y][x + len(text) :]

    def centre(y: int, value: str, style: str | Style) -> None:
        text = Text(value, style=style, no_wrap=True)
        text.truncate(inside, overflow='ellipsis')
        put((width - len(text)) // 2, y, text)

    # Each side grows symmetrically from its corners, never wrapping a border.
    fraction = min(1.0, progress / 0.55)
    for x in range(left + 1, right):
        if min(x - left, right - x) <= (right - left) * fraction / 2:
            for y in (top, bottom):
                put(x, y, Text('✦' if x in (left + 2, right - 2) else '═', style=frame))
    for y in range(top + 1, bottom):
        if min(y - top, bottom - y) <= (bottom - top) * fraction / 2:
            for x in (left, right):
                put(x, y, Text('║', style=frame))
            put(right - 2, y, Text('│', style=colours.muted.hex))
    for x, y, glyph in (
        (left, top, '╔'),
        (right, top, '╗'),
        (left, bottom, '╚'),
        (right, bottom, '╝'),
    ):
        put(x, y, Text(glyph, style=frame))
    small = height < 25
    centre(top + 1 if small else top + 2, '✦  ✣  ✦', title_ink)
    centre(top + 3 if small else top + 5, 'መጽሐፍ ቅዱስ', Style(color=title_ink, bold=True))
    centre(top + 4 if small else top + 7, 'The Holy Bible', quiet)
    centre(top + 5 if small else top + 9, '─ ❖ ─', quiet)
    wrapped = Text(epigraph).wrap(Console(), inside - 2)
    epigraph_y = top + 7 if small else top + 12
    for index, line in enumerate(wrapped):
        centre(epigraph_y + index, line.plain, quiet + Style(italic=True))
    centre(epigraph_y + len(wrapped) + 1, format_reference(EPIGRAPH), quiet)
    action_y = bottom - 5
    action_style = Style(color=title_ink, bold=True, underline=selected == 0)
    centre(action_y, 'Continue reading' if continuing else 'Begin', action_style)
    centre(action_y + 1, position, action_style)
    targets = [(left + 2, action_y, right - 1, action_y + 2)]
    names = ('Books', 'Search', 'Plans', 'Settings')
    total = sum(map(len, names)) + 6
    x = (width - total) // 2
    for index, name in enumerate(names, 1):
        put(x, bottom - 2, Text(name, style=quiet + Style(underline=True, bold=selected == index)))
        targets.append((x, bottom - 2, x + len(name), bottom - 1))
        x += len(name) + 2
    centre(bottom + 1, 'Esc · close', quiet + Style(underline=True, bold=selected == 5))
    targets.append(((width - 11) // 2, bottom + 1, (width - 11) // 2 + 11, bottom + 2))
    return lines, targets


class Cover(Widget, inherit_bindings=False):
    def render(self) -> Text:
        screen = self.screen
        assert isinstance(screen, TitleScreen)
        lines, _ = screen.art()
        offset = screen.wipe_offset
        text = Text('\n', no_wrap=True).join(line[offset:] for line in lines)
        if offset:
            for y in range(len(lines)):
                start = y * (self.size.width + 1)
                text.stylize(
                    Style(
                        color=screen.colours().effects.glow.hex,
                        bgcolor=screen.colours().effects.background.hex,
                        bold=True,
                    ),
                    start,
                    start + min(2, self.size.width),
                )
        return text

    async def on_click(self, event: events.Click) -> None:
        event.stop()
        screen = self.screen
        assert isinstance(screen, TitleScreen)
        if screen.skip():
            return
        _, targets = screen.art()
        for index, (x1, y1, x2, y2) in enumerate(targets):
            if x1 <= event.x < x2 and y1 <= event.y < y2:
                screen.selected = index
                await screen.activate()
                return


class TitleScreen(ModalScreen[None], Page, inherit_bindings=False):
    BINDINGS = [
        Binding('enter', 'open', 'Open'),
        Binding('escape', 'close', 'Quit'),
        Binding('tab', 'next', 'Next link', show=False),
        Binding('b', "page('books')", 'Books'),
        Binding('/', "page('search')", 'Search'),
        Binding('p', "page('plans')", 'Plans'),
        Binding('s', "page('settings')", 'Settings'),
    ]

    def __init__(self, *, continuing: bool = True) -> None:
        super().__init__()
        self.continuing = continuing
        self.clock: Callable[[], float] = monotonic
        self.started = 0.0
        self.progress = 0.0
        self.phase = 'entrance'
        self.selected = 0
        self.wipe_offset = 0
        self.motion_timer: Timer | None = None
        self.suspended_at: float | None = None

    def compose(self) -> ComposeResult:
        yield Cover(id='cover')

    def colours(self) -> Palette:
        variables = self.app.get_css_variables()
        return palette(
            variables['foreground'],
            variables['secondary'],
            variables['accent'],
            variables['background'],
            effect_colours(self.app.current_theme),
        )

    def art(self) -> tuple[list[Text], list[tuple[int, int, int, int]]]:
        return cover_art(
            self.app.size.width,
            self.app.size.height,
            self.progress,
            self.colours(),
            self.eb.epigraph,
            format_reference(self.eb.reference) if self.continuing else 'Genesis 1',
            self.continuing,
            self.selected,
        )

    def on_mount(self) -> None:
        self.started = self.clock()
        self.motion_timer = self.set_interval(FRAME_INTERVAL, self.tick)
        self.set_focus(None)
        if self.eb.settings.reduce_motion:
            self.finish_entrance()

    def finish_entrance(self) -> None:
        self.progress = 1.0
        self.phase = 'rest'
        if self.motion_timer:
            self.motion_timer.pause()
        self.query_one(Cover).refresh()

    def finish_opening(self) -> None:
        if self.motion_timer:
            self.motion_timer.pause()
        self.phase = 'done'
        self.dismiss()

    def tick(self) -> None:
        if self.app.screen is not self:
            return
        elapsed = max(0.0, self.clock() - self.started)
        if self.phase == 'entrance':
            self.progress = min(1.0, (elapsed + 1e-9) / ENTRANCE_DURATION)
            if self.progress == 1 or self.eb.settings.reduce_motion:
                self.finish_entrance()
        elif self.phase == 'opening':
            if elapsed >= OPEN_DURATION - 1e-9 or self.eb.settings.reduce_motion:
                self.finish_opening()
                return
            self.wipe_offset = int(self.app.size.width * elapsed / OPEN_DURATION + 1e-9)
            cover = self.query_one(Cover)
            cover.styles.offset = (self.wipe_offset, 0)
            cover.styles.width = self.app.size.width - self.wipe_offset
        self.query_one(Cover).refresh()

    def skip(self) -> bool:
        if self.phase == 'entrance':
            self.finish_entrance()
            return True
        if self.phase == 'opening':
            self.finish_opening()
            return True
        return False

    async def activate(self) -> None:
        if self.skip():
            return
        if self.selected == 5:
            self.app.exit()
        elif self.selected:
            await self.eb.open_page(('books', 'search', 'plans', 'settings')[self.selected - 1])
        elif self.eb.settings.reduce_motion:
            self.finish_opening()
        else:
            self.phase = 'opening'
            self.started = self.clock()
            assert self.motion_timer is not None
            self.motion_timer.resume()

    async def on_key(self, event: events.Key) -> None:
        # Consume the skipping key: it must never leak into the reader or a link.
        event.stop()
        event.prevent_default()
        if self.skip():
            return
        if event.key == 'escape':
            self.app.exit()
        elif event.key in ('tab', 'right', 'down'):
            self.selected = (self.selected + 1) % 6
        elif event.key in ('left', 'up'):
            self.selected = (self.selected - 1) % 6
        elif event.key in ('enter', 'space'):
            await self.activate()
        elif event.character in ('b', '/', 'p', 's'):
            await self.eb.open_page(
                {'b': 'books', '/': 'search', 'p': 'plans', 's': 'settings'}[event.character]
            )
        self.query_one(Cover).refresh()

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.skip()

    def on_screen_suspend(self) -> None:
        self.suspended_at = self.clock()
        if self.motion_timer:
            self.motion_timer.pause()

    def on_screen_resume(self) -> None:
        if self.suspended_at is not None:
            self.started += self.clock() - self.suspended_at
            self.suspended_at = None
        if self.motion_timer and self.phase in ('entrance', 'opening'):
            self.motion_timer.resume()
        if self.is_mounted:
            self.query_one(Cover).refresh()
