# Batch 6 review — in-app Anthropic credentials

Settings → Translation & Touch now accepts an Anthropic key in a masked field.
Save key or Enter saves it; the saved view shows only `sk-ant-…` plus the last four
characters, with Replace and Remove controls. Replace opens a blank field, Cancel
preserves the old key, and leaving Settings clears any unsaved draft.

## Storage and precedence

- The credential is separate from Settings and settings.json, at the call-time XDG
  config path `ebible/anthropic_key`. The file contains only the key, without newline.
- Atomic saves create a unique temporary file with exclusive `os.open(..., 0o600)`
  before writing, flush/fsync, then replace the target. No chmod is used. Tests check
  both the creation mode and actual permissions with permissive and restrictive
  umasks, inspect the temporary file before replacement, and prohibit chmod.
- Missing-file reads and removals are harmless. Failed writes leave the old key
  intact and clean up temporary files. Read/save/remove errors use fixed messages
  that do not echo OS exception details. This is private plaintext storage, not
  encryption; README describes that distinction.
- A nonempty ANTHROPIC_API_KEY wins over a saved key, without needing to read the
  saved file. Empty environment variables behave as unset, matching prior behavior.
  Automatic backend selection treats either source as Claude credentials. Google
  and Off selections remain explicit overrides.
- The key is passed as `api_key=...` to the Anthropic client. Application code does
  not mutate the environment. Removing a saved key never removes an environment
  key. The source label says which credential wins, or reports Google/no-backend
  fallback; explicit Google/Off selection is also noted beside an available key.

## Validation and disclosure protection

Saving performs only local validation: `sk-ant-` prefix, nonempty suffix, and no
Unicode whitespace. The nonempty suffix is a small judgment beyond the two named
checks: a bare prefix cannot be a credential. There is no length/character-set or
network validity check. Paste is preserved exactly for validation; trailing spaces,
newlines and later pasted lines are rejected instead of silently trimmed.

Secrets are never placed in the Settings dataclass or JSON. The credential holder
excludes its value from both ordinary and Rich representations. Password entry
uses `password=True`, never prefills a saved value, and clears after saving/leaving.
Input Changed/Submitted/Blurred messages carry no key value. Textual logs events
before dispatch, so incoming paste events are replaced with a redacted-repr event
before queuing, and the original event payload is cleared. A Pilot test captures
that actual pre-dispatch log path, including app-level paste forwarding.

SDK construction/request errors are converted to fixed actionable messages with
original exception chains suppressed. Stop reasons are not echoed; cleanup errors
are suppressed. Fake SDK errors deliberately include a full fake key, and tests
check exception text, formatted tracebacks, logs and the inline reader error.
The implementation retains the prior backend deadlines and translation behavior.

## Interaction decisions

Preferences still save immediately; credentials require explicit Save/Enter to
avoid writing incomplete keys. The settings subtitle now makes that distinction.
Cancel and Escape do not save. Remove is direct and affects only the saved key;
no additional confirmation or network check was introduced. Replace/Remove stay
available for a saved key even when an environment key takes precedence. Existing
translations remain session-only; adding/removing a key does not clear them or
trigger a request. The next uncached verse resolves the current key normally.

All credential file access from Settings runs in a thread. The UI renders only a
masked hint and source/error text; the draft stays in the password widget until
saved or discarded. No new dependency was added.

## Regression and visual verification

There are **19 new unit cases and 10 new Pilot cases**. They cover private atomic
creation/replacement, permissions under different umasks, removal, invalid input,
missing/read/write errors, precedence and environment preservation, explicit SDK
credentials, safe repr/JSON/exception/log output, restart, cancel, masked rendering,
fallback labels, and translation errors through the real worker with a fake client.
Saving is tested with backend selection forbidden, proving no translation occurs.

Six isolated mutation checks failed as expected when changing creation to 0644,
reversing environment precedence, disabling password masking, skipping removal,
bypassing validation, or allowing the paste event repr to expose its payload.
These changes were made only in `/tmp/ebible-b6-mutations`, not the working tree.

Smoke adds entry, saved, replacement, invalid-input, environment-precedence and
removed-key states. It uses obviously fake credentials and temporary XDG paths,
removes the invoking shell's API key from its temporary environment, then restores
that environment. Every one of the **198 SVGs** is checked for full fake-key strings
before writing. A separate scan also checks joined SVG/XML text. Pilot also checks screenshot text, widget renders/reprs, messages,
Settings repr, JSON and captured logs.

Reviewed all six new phone states in meskel, parchment and lalibela, plus the wide
parchment saved-key view. Masking, suffix labels, source text and inline errors fit
without horizontal clipping. The settings page retains normal vertical scrolling.
No unrelated layout redesign or scripture changes were made.

## Gates, protected data and limits

Required gates ran in the root `.venv` (Python 3.14.7, Textual 8.2.8):

- `ruff check src tests tools`: all checks passed.
- `ruff format --check src tests`: 58 files already formatted.
- `mypy src`: no issues in 40 source files.
- `pytest -q`: **377 passed in 272.93s**, including 149 UI cases.
- `python tools/smoke.py --out /tmp/ebible-smoke`: **198 SVGs passed**.

The full gate output, including smoke, is in `/tmp/b6-final-gates.log`; Status is
recorded in AGENTS.md.
Smoke writes 33 states × two sizes × three themes: 198 SVGs plus manifest.txt.
The full directory listing is `/tmp/ebible-smoke-listing.txt`.

The packaged database remains 12,521,472 bytes, SHA-256
`46da43911496d300784fd303a69cbf5a108486a06a8e45ea2c82efa1c11e9997`.
Schema, canon, raw Amharic, source-issues documentation and both guide copies are
unchanged. The full suite retains the original-data checksum/integrity tests.

Batch 6 used fake credentials and clients only. No real Anthropic request or
physical Termux session was exercised. Claude's independently reported Batch 5
Google translation/toggle/actions test in tmux at 50×30 is recorded separately.
Implementation commits: `7a5b5c4`, `5eea4a8`, `777a63f`, followed by the status/review
commit. Nothing was pushed or published.
