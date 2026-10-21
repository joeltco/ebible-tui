# eBible v2

A Termux-first Amharic and English terminal reader for the 81-book Ethiopian
Orthodox Tewahedo canon. **Batch 1 is the foundation:** typed core services,
read-only scripture, personal data, translation workers, and a bootable
placeholder. Reader screens and custom Ethiopian themes arrive in batch 2.

Requires Python 3.11 or newer. Install locally in the repository's virtualenv:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
ebible --version
ebible
# A reference is validated and displayed by the placeholder:
ebible 'john 3:16' --theme textual-light
ebible 'ዘፍ 1'
```

Use the Quit button, `q`, or Escape to leave the placeholder. Both phone-size
50×30 and desktop-size 120×40 terminals are tested. Built-in Textual themes work
with `--theme`; the custom themes and persisted UI preferences are batch 2 work.

The bundled `src/ebible/data/bible.db` is authoritative and read-only: 39,169
verses, with reviewed English for 20,443. Never rebuild or modify it. The raw
Amharic source and canon rows are preserved. Live English is stored separately
in `user.db`, with backend and timestamp provenance. Display precedence is
bundled English, live English, then an explicit untranslated placeholder.

Settings resolve at call time under `$XDG_CONFIG_HOME/ebible` (default
`~/.config/ebible`); personal data uses `$XDG_DATA_HOME/ebible` (default
`~/.local/share/ebible`). Relative or empty XDG variables use the defaults.
The placeholder does not create personal data or start translations.

Optional live translation:

```sh
pip install -e '.[claude]'
# Set ANTHROPIC_API_KEY in your environment before using the Claude backend.
```

The core service selects Claude when an API key is present, otherwise
translate-shell's `trans` if available, otherwise off. Explicit settings are
`auto`, `claude`, `google`, and `off`. Claude uses `claude-sonnet-5-5` and the
packaged, verbatim translation guide. Backends are lazy-loaded. Tests use fake
clients and subprocesses; they never call translation services.

The relocated offline scripts' read commands work from any current directory:

```sh
python tools/translation/translate.py status
python tools/translation/translate.py pull john 3
python tools/translation/translate.py next --count 5
```

Only import/path repairs were made to the inherited pipeline. Its `translate.py`
legacy `open_writable` import now aliases the read-only connection helper, so
`push` cannot modify the bundled database. Other inherited maintenance scripts
retain their original write logic and must not be run against the protected DB.
No offline repair, build, seal, or push operation was run for batch 1.

Run all gates from the activated virtualenv:

```sh
ruff check src tests tools
ruff format --check src tests
mypy src
pytest -q
python tools/smoke.py --out /tmp/ebible-smoke
```

See [foundation decisions](docs/FOUNDATION.md) for API conventions, boundaries,
and the choices left open by the specification. See [AGENTS.md](AGENTS.md) for
the binding architecture and the batch status.
