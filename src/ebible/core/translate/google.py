"""translate-shell fallback, single-verse requests with bounded timeout."""

import shutil
import subprocess
from collections.abc import Mapping

from ebible.canon import Book
from ebible.core.translate.base import TranslationError, validate_alignment
from ebible.core.translate.query import parse_query_variants


class GoogleBackend:
    name = 'google'

    def __init__(self, executable: str | None = None, *, timeout: float = 20) -> None:
        self.executable = executable
        if timeout <= 0:
            raise ValueError('Timeout must be positive')
        self.timeout = timeout

    def translate_verse(
        self, book: Book, chapter: int, verses_am: Mapping[int, str], target: int
    ) -> dict[int, str]:
        if target not in verses_am:
            raise TranslationError('Target verse is missing from chapter context')
        executable = self.executable or shutil.which('trans')
        if not executable:
            raise TranslationError('Install translate-shell (trans), then press Enter to retry.')
        try:
            result = subprocess.run(
                [executable, '-brief', '-engine', 'google', 'am:en'],
                input=verses_am[target],
                capture_output=True,
                encoding='utf-8',
                check=True,
                timeout=self.timeout,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise TranslationError(
                'Translation failed or timed out. Check your connection and translate-shell, then press Enter to retry.'
            ) from exc
        translated = {target: result.stdout.strip()}
        validate_alignment({target: verses_am[target]}, translated)
        return translated

    def translate_query(self, query: str) -> tuple[str, ...]:
        executable = self.executable or shutil.which('trans')
        if not executable:
            raise TranslationError(
                'Install translate-shell (trans) or set an Anthropic key in Settings.'
            )
        try:
            result = subprocess.run(
                [executable, '-b', 'en:am'],
                input=query,
                capture_output=True,
                encoding='utf-8',
                check=True,
                timeout=self.timeout,
            )
        except (OSError, subprocess.SubprocessError):
            raise TranslationError(
                'Query translation failed or timed out. Check your connection and translate-shell.'
            ) from None
        return parse_query_variants(result.stdout, limit=1)
