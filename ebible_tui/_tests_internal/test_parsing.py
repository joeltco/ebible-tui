from ebible_tui.core.bible.parsing import parse_verses


def test_parse_verses_minimal() -> None:
    text = '1. መጀመሪያ የነበረው ቃል ነበረ።\n2. እግዚአብሔር በመጀመሪያ ፈጠረ።'
    verses = parse_verses(text)
    assert verses and verses[0][0] == 1 and verses[1][0] == 2
