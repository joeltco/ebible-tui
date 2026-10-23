"""Keep typing local to controls and remove modifier-only desktop bindings."""

from collections.abc import Iterable

from rich.text import Text
from textual import events
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Input, OptionList, Select, TextArea

from ebible.ui.themes import THEMES


def phone_bindings(bindings: Iterable[BindingType]) -> list[BindingType]:
    allowed = {
        'left',
        'right',
        'up',
        'down',
        'backspace',
        'delete',
        'enter',
        'space',
        'tab',
        'escape',
    }
    return [binding for binding in Binding.make_bindings(bindings) if binding.key in allowed]


class TextInput(Input, inherit_bindings=False):
    BINDINGS = phone_bindings(Input.BINDINGS)


class SecretInput(TextInput):
    """Masked entry with no credential payload in queued/loggable input messages."""

    def __init__(self, *, id: str) -> None:
        super().__init__(password=True, placeholder='Paste your key', id=id)

    def post_message(self, message: Message) -> bool:
        if isinstance(message, (Input.Changed, Input.Submitted, Input.Blurred)):
            message.value = ''
            message.validation_result = None
        return super().post_message(message)

    def _on_paste(self, event: events.Paste) -> None:
        # Ordinary Input silently drops later lines. Preserve them for validation.
        self.replace(event.text, *self.selection)
        event.text = ''
        event.stop()

    def on_unmount(self) -> None:
        self.value = ''


class NoteArea(TextArea, inherit_bindings=False):
    BINDINGS = phone_bindings(TextArea.BINDINGS)


# Textual's scroll containers add desktop modifier bindings. Strip those while
# retaining ordinary arrows; nested Select overlays are handled after mounting.


class PhoneScroll(VerticalScroll, inherit_bindings=False):
    BINDINGS = phone_bindings(VerticalScroll.BINDINGS)


class PassageList(OptionList, inherit_bindings=False):
    BINDINGS = phone_bindings(OptionList.BINDINGS)


class Choice(Select[str]):
    def on_mount(self) -> None:
        for node in self.walk_children(with_self=True):
            for key in list(node._bindings.key_to_bindings):
                if any(modifier in key for modifier in ('ctrl+', 'alt+', 'super+')):
                    del node._bindings.key_to_bindings[key]


class ThemeChoice(Choice):
    """Disabled group headings preserve Select's native keyboard and touch behavior."""

    GROUPS = ('__ebible_themes__', '__more_themes__')

    def __init__(self, names: Iterable[str], *, value: str, id: str) -> None:
        custom = {theme.name for theme in THEMES}
        names = tuple(names)
        options = [(Text('eBible themes', style='bold'), self.GROUPS[0])]
        options.extend(
            (Text(name.replace('-', ' ').title()), name) for name in names if name in custom
        )
        options.append((Text('More themes', style='bold'), self.GROUPS[1]))
        options.extend(
            (Text(name.replace('-', ' ').title()), name) for name in names if name not in custom
        )
        super().__init__(options, value=value, allow_blank=False, id=id)

    def _setup_options_renderables(self) -> None:
        super()._setup_options_renderables()
        overlay = self.query_one(OptionList)
        for index, (_, value) in enumerate(self._options):
            if value in self.GROUPS:
                overlay.get_option_at_index(index).disabled = True
