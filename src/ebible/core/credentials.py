"""Anthropic credentials, separate from preferences and never printable in full."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import uuid4

from ebible.paths import config_dir


class CredentialError(ValueError):
    """A safe, actionable message without credential or OS exception details."""


@dataclass(frozen=True, slots=True)
class AnthropicKey:
    value: str = field(repr=False)
    source: Literal['environment', 'saved']

    @property
    def masked(self) -> str:
        return 'sk-ant-…' + self.value[-4:]


def key_path() -> Path:
    return config_dir() / 'anthropic_key'


def read_saved_key() -> AnthropicKey | None:
    try:
        value = key_path().read_text(encoding='utf-8')
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError):
        raise CredentialError('Cannot read saved key. Replace or remove it in Settings.') from None
    return AnthropicKey(value, 'saved') if value else None


def active_key() -> AnthropicKey | None:
    value = os.environ.get('ANTHROPIC_API_KEY')
    return AnthropicKey(value, 'environment') if value else read_saved_key()


def save_key(value: str) -> None:
    if not value.startswith('sk-ant-') or len(value) <= 7 or any(c.isspace() for c in value):
        raise CredentialError('Key must start with sk-ant- and contain no whitespace.')
    target = key_path()
    temporary = target.with_name('.anthropic-key-' + uuid4().hex)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Private from the instant of creation, including when replacing an old file.
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except (OSError, UnicodeError):
        raise CredentialError('Could not save key. Check access to the config directory.') from None
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def remove_key() -> None:
    try:
        key_path().unlink(missing_ok=True)
    except OSError:
        raise CredentialError(
            'Could not remove key. Check access to the config directory.'
        ) from None
