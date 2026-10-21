"""The 81-book Ethiopian Orthodox Tewahedo canon.

Book order follows the Ethiopian canon, which is not the Western order: Jubilees
and Enoch sit among the historical books, the Meqabyan books follow Esther, and
the catholic epistles come after 3 John rather than before Hebrews. The `id` is
that canonical position and is what the asset directories are numbered by.

English names are the established scholarly renderings. Books outside the 66-book
protestant canon are flagged `deuterocanonical` because they have no widely
available English translation to bundle -- see `Book.deuterocanonical`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Section(StrEnum):
    """Traditional groupings, used for the book-picker's headings."""

    LAW = 'Law'
    HISTORY = 'History'
    WISDOM = 'Wisdom'
    PROPHETS = 'Prophets'
    GOSPELS = 'Gospels'
    EPISTLES = 'Epistles'
    APOCALYPSE = 'Apocalypse'


@dataclass(frozen=True, slots=True)
class Book:
    id: int
    slug: str
    name_am: str
    name_en: str
    section: Section
    deuterocanonical: bool = False

    @property
    def display(self) -> str:
        return f'{self.name_am}  ·  {self.name_en}'


_L, _H, _W, _P = Section.LAW, Section.HISTORY, Section.WISDOM, Section.PROPHETS
_G, _E, _A = Section.GOSPELS, Section.EPISTLES, Section.APOCALYPSE

# (id, slug, Amharic, English, section, deuterocanonical)
_ROWS: tuple[tuple[int, str, str, str, Section, bool], ...] = (
    (1, 'genesis', 'ኦሪት ዘፍጥረት', 'Genesis', _L, False),
    (2, 'exodus', 'ኦሪት ዘጸአት', 'Exodus', _L, False),
    (3, 'leviticus', 'ኦሪት ዘሌዋውያን', 'Leviticus', _L, False),
    (4, 'numbers', 'ኦሪት ዘኊልቊ', 'Numbers', _L, False),
    (5, 'deuteronomy', 'ኦሪት ዘዳግም', 'Deuteronomy', _L, False),
    (6, 'joshua', 'መጽሐፈ ኢያሱ', 'Joshua', _H, False),
    (7, 'judges', 'መጽሐፈ መሳፍንንት', 'Judges', _H, False),
    (8, 'ruth', 'መጽሐፈ ሩት', 'Ruth', _H, False),
    (9, '1-samuel', 'ሳሙኤል ቀዳማዊ', '1 Samuel', _H, False),
    (10, '2-samuel', 'ሳሙኤል ካልእ', '2 Samuel', _H, False),
    (11, '1-kings', 'ነገሥት ቀዳማዊ', '1 Kings', _H, False),
    (12, '2-kings', 'ነገሥት ካልዕ', '2 Kings', _H, False),
    (13, '1-chronicles', 'ዜና መዋዕል ቀዳማዊ', '1 Chronicles', _H, False),
    (14, '2-chronicles', 'ዜና መዋዕል ካልዕ', '2 Chronicles', _H, False),
    (15, 'jubilees', 'መጽሐፈ ኩፋሌ', 'Jubilees', _H, True),
    (16, 'enoch', 'መጽሐፈ ሄኖክ', 'Enoch', _H, True),
    (17, 'ezra', 'መጽሐፈ ዕዝራ', 'Ezra', _H, False),
    (18, 'nehemiah', 'መጽሐፈ ነህምያ', 'Nehemiah', _H, False),
    (19, 'ezra-sutuel', 'እዝራ ሱቱኤል', 'Ezra Sutuel', _H, True),
    (20, 'ezra-kalie', 'እዝራ ካልእ', 'Ezra Kalie', _H, True),
    (21, 'tobit', 'መጽሐፈ ጦቢት', 'Tobit', _H, True),
    (22, 'judith', 'መጽሐፈ ዮዲት', 'Judith', _H, True),
    (23, 'esther', 'መጽሐፈ አስቴር', 'Esther', _H, False),
    (24, '1-meqabyan', 'መቃብያን ቀዳማዊ', '1 Meqabyan', _H, True),
    (25, '2-meqabyan', 'መቃብያን ካልዕ', '2 Meqabyan', _H, True),
    (26, '3-meqabyan', 'መቃብያን ሳልስ', '3 Meqabyan', _H, True),
    (27, 'job', 'መጽሐፈ ኢዮብ', 'Job', _W, False),
    (28, 'psalms', 'መዝሙረ ዳዊት', 'Psalms', _W, False),
    (29, 'proverbs', 'መጽሐፈ ምሳሌ', 'Proverbs', _W, False),
    (30, 'reproof', 'መጽሐፈ ተግሳጽ', 'Reproof', _W, True),
    (31, 'wisdom', 'መጽሐፈ ጥበብ', 'Wisdom of Solomon', _W, True),
    (32, 'ecclesiastes', 'መጽሐፈ መክብብ', 'Ecclesiastes', _W, False),
    (33, 'song-of-songs', 'ማሐልየ መሓልይ', 'Song of Songs', _W, False),
    (34, 'sirach', 'መጽሐፈ ሲራክ', 'Sirach', _W, True),
    (35, 'isaiah', 'ትንቢተ ኢሳይያስ', 'Isaiah', _P, False),
    (36, 'jeremiah', 'ትንቢተ ኤርምያስ', 'Jeremiah', _P, False),
    (37, 'lamentations', 'ሰቆቃወ ኤርምያስ', 'Lamentations', _P, False),
    (38, 'rest-of-jeremiah', 'ተረፈ ኤርምያስ', 'Rest of Jeremiah', _P, True),
    (39, 'baruch', 'መጽሐፈ ባሮክ', 'Baruch', _P, True),
    (40, 'rest-of-baruch', 'ተረፈ ባሮክ', 'Rest of Baruch', _P, True),
    (41, 'ezekiel', 'ትንቢተ ሕዝቅኤል', 'Ezekiel', _P, False),
    (42, 'daniel', 'ትንቢተ ዳንኤል', 'Daniel', _P, False),
    (43, 'hosea', 'ትንቢተ ሆሴዕ', 'Hosea', _P, False),
    (44, 'amos', 'ትንቢተ ዓሞጽ', 'Amos', _P, False),
    (45, 'micah', 'ትንቢተ ሚክያስ', 'Micah', _P, False),
    (46, 'joel', 'ትንቢተ ኢዮኤል', 'Joel', _P, False),
    (47, 'obadiah', 'ትንቢተ ዐብድዩ', 'Obadiah', _P, False),
    (48, 'jonah', 'ትንቢተ ዮናስ', 'Jonah', _P, False),
    (49, 'nahum', 'ትንቢተ ናሆም', 'Nahum', _P, False),
    (50, 'habakkuk', 'ትንቢተ ዕንባቆም', 'Habakkuk', _P, False),
    (51, 'zephaniah', 'ትንቢተ ሶፎንያስ', 'Zephaniah', _P, False),
    (52, 'haggai', 'ትንቢተ ሐጌ', 'Haggai', _P, False),
    (53, 'zechariah', 'ትንቢተ ዘካርያስ', 'Zechariah', _P, False),
    (54, 'malachi', 'ትንቢተ ሚልክያስ', 'Malachi', _P, False),
    (55, 'matthew', 'የማቴዎስ ወንጌል', 'Matthew', _G, False),
    (56, 'mark', 'የማርቆስ ወንጌል', 'Mark', _G, False),
    (57, 'luke', 'የሉቃስ ወንጌል', 'Luke', _G, False),
    (58, 'john', 'የዮሐንስ ወንጌል', 'John', _G, False),
    (59, 'acts', 'የሐዋርያት ሥራ', 'Acts', _H, False),
    (60, 'romans', 'ወደ ሮሜ', 'Romans', _E, False),
    (61, '1-corinthians', '1ኛ ቆሮንቶስ', '1 Corinthians', _E, False),
    (62, '2-corinthians', '2ኛ ቆሮንቶስ', '2 Corinthians', _E, False),
    (63, 'galatians', 'ወደ ገላትያ', 'Galatians', _E, False),
    (64, 'ephesians', 'ወደ ኤፌሶን', 'Ephesians', _E, False),
    (65, 'philippians', 'ወደ ፊልጵስዩስ', 'Philippians', _E, False),
    (66, 'colossians', 'ወደ ቆላስይስ', 'Colossians', _E, False),
    (67, '1-thessalonians', '1ኛ ተሰሎንቄ', '1 Thessalonians', _E, False),
    (68, '2-thessalonians', '2ኛ ተሰሎንቄ', '2 Thessalonians', _E, False),
    (69, '1-timothy', '1ኛ ጢሞቴዎ', '1 Timothy', _E, False),
    (70, '2-timothy', '2ኛ ጢሞቴዎስ', '2 Timothy', _E, False),
    (71, 'titus', 'ወደ ቲቶ', 'Titus', _E, False),
    (72, 'philemon', 'ወደ ፊልሞና', 'Philemon', _E, False),
    (73, 'hebrews', 'ወደ ዕብራውያን', 'Hebrews', _E, False),
    (74, '1-peter', '1ኛ ጴጥሮስ', '1 Peter', _E, False),
    (75, '2-peter', '2ኛ ጴጥሮስ', '2 Peter', _E, False),
    (76, '1-john', '1ኛ ዮሐንስ', '1 John', _E, False),
    (77, '2-john', '2ኛ ዮሐንስ', '2 John', _E, False),
    (78, '3-john', '3ኛ ዮሐንስ', '3 John', _E, False),
    (79, 'james', 'የያዕቆብ መልእክት', 'James', _E, False),
    (80, 'jude', 'የይሁዳ መልእክት', 'Jude', _E, False),
    (81, 'revelation', 'የዮሐንስ ራእይ', 'Revelation', _A, False),
)

BOOKS: tuple[Book, ...] = tuple(Book(*row) for row in _ROWS)

BY_ID: dict[int, Book] = {b.id: b for b in BOOKS}
BY_SLUG: dict[str, Book] = {b.slug: b for b in BOOKS}


def by_id(book_id: int) -> Book:
    return BY_ID[book_id]


def by_slug(slug: str) -> Book:
    return BY_SLUG[slug]
