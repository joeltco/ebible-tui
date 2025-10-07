eBible TUI
==========

A terminal Textual UI for reading and translating the Ethiopian Orthodox Bible (81 books).
Navigate Books and Chapters on the left, read Verses on the right, and translate a selected verse.

Features
- 81-book Ethiopian Orthodox canon bundled as plain text assets.
- Books and Chapters navigation panes.
- Verses panel with wrapping and scrolling.
On-demand translation via Google Translate using translate-shell (`trans`).
- Async translation to keep the UI responsive.
- Clean layout with consistent bordered panels.

Prerequisites
- Python 3.12 or newer available in Termux.
- translate-shell package must be installed (`pkg install translate-shell` on Termux).
- No model files required; translations are done online via Google services.

Install (local dev)
- From the project root:
    $ pip install --upgrade -e .

Run
- From the project root:
    $ ebible
- Or:
    $ python -m ebible_tui

Keyboard
- q: quit
- p / n: move focus left/right between panes
- g / G: jump to top / bottom
- Enter on a verse: translate verse into the Translation box

Config
- Optional file: ~/.config/ebible/config.yaml
  Keys:
    bible_dir: absolute path to a Bible81 directory (overrides packaged assets)

Translation Backend
- App calls ebible_tui.core.translate.translate / translate_async.
Default backend is Google Translate through translate-shell. Requires internet connectivity.
  1) reads input text on stdin
  2) maps language tags for NLLB model
Optional: override default command with environment variable:
    EBIBLE_GOOGLE_TRANS_CMD=/absolute/path/to/trans
    EBIBLE_TRANSLATOR=/absolute/path/to/amtr
Supported language tags: am, en (extendable in code).

Project Layout (high level)
- ebible_tui/core/bible: assets resolution, parsing, refs, English canon names
- ebible_tui/core/translate: backend interface and Amtr implementation
- ebible_tui/core/reader.py: list books/chapters, read chapter text
- ebible_tui/ui/widgets: NavPane, VersePanel, TranslationPanel, TitleBar
- ebible_tui/ui/styles/app.tcss: layout and theming
- ebible_tui/assets/Bible81: bundled text files
- ebible_tui/tests: lightweight tests for parsing, refs, reader, translate

Maintenance
- Lint:
    $ ruff check .
- Type check:
    $ mypy ebible_tui
- Tests:
    $ pytest -q

Troubleshooting
- No books listed: verify packaged assets exist at ebible_tui/assets/Bible81 or set bible_dir in config.
- Translation not working: ensure `trans` is installed and functional (`trans -b am:en "ሰላም ዓለም!"`).
- TUI layout quirks: see ebible_tui/ui/styles/app.tcss overrides at the end of the file.

License
- Personal project; choose and update a license as needed.

Credits
- Built with Textual and Rich.
- Translation powered by a local NLLB-200 distilled 600M model.
