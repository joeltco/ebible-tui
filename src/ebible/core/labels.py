"""Consistent English count labels for status and error messages."""


def count_label(count: int, singular: str, plural: str | None = None) -> str:
    return f'{count} {singular if count == 1 else plural or singular + "s"}'
