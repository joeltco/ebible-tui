"""translate-shell fallback, sequential per-verse requests with bounded timeout."""

import shutil
import subprocess
from collections.abc import Mapping

from ebible.canon import Book
from ebible.core.translate.base import TranslationError, validate_alignment


class GoogleBackend:
    name = 'google'

    def __init__(self, executable: str | None = None, *, timeout: float = 20) -> None:
        self.executable = executable
        if timeout <= 0:
            raise ValueError('Timeout must be positive')
        self.timeout = timeout

    def translate_chapter(
        self, book: Book, chapter: int, verses_am: Mapping[int, str]
    ) -> dict[int, str]:
        if not verses_am:
            return {}
        executable = self.executable or shutil.which('trans')
        if not executable:
            raise TranslationError('translate-shell (trans) is not on PATH')
        translated: dict[int, str] = {}
        for number, text in sorted(verses_am.items()):
            try:
                result = subprocess.run(
                    [executable, '-brief', '-engine', 'google', 'am:en'],
                    input=text,
                    capture_output=True,
                    encoding='utf-8',
                    check=True,
                    timeout=self.timeout,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise TranslationError(
                    f'Google translation failed at {book.name_en} {chapter}:{number}: {exc}'
                ) from exc
            translated[number] = result.stdout.strip()
        validate_alignment(verses_am, translated)
        return translated
