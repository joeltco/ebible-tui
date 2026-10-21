"""Keep typing local to controls and remove modifier-only desktop bindings."""

from collections.abc import Iterable

from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.widgets import Input, OptionList, Select, TextArea


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
