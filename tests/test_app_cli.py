import subprocess
import sys
from pathlib import Path

import pytest

from ebible import __version__
from ebible.__main__ import main
from ebible.app import EBibleApp
from ebible.core.models import VerseRef


def test_version_help_and_invalid_arguments(capsys):
    with pytest.raises(SystemExit) as exc:
        main(['--version'])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f'ebible {__version__}'
    with pytest.raises(SystemExit) as exc:
        main(['--help'])
    assert exc.value.code == 0
    assert 'REF' in capsys.readouterr().out
    for args in (['unknown'], ['john', '99'], ['--theme', 'nonexistent-theme']):
        with pytest.raises(SystemExit) as exc:
            main(args)
        assert exc.value.code == 2
        assert 'error:' in capsys.readouterr().err


@pytest.mark.parametrize('args', [['john 3:16'], ['john', '3:16']])
def test_cli_passes_reference_to_app(args, monkeypatch):
    seen = []

    def run(app):
        seen.append(app.reference)

    monkeypatch.setattr(EBibleApp, 'run', run)
    assert main(args) == 0
    assert seen == [VerseRef(58, 3, 16)]


def test_default_cli_and_theme(monkeypatch):
    seen = []
    monkeypatch.setattr(EBibleApp, 'run', lambda app: seen.append((app.reference, app.theme)))
    assert main(['--theme', 'textual-light']) == 0
    assert seen == [(VerseRef(1), 'textual-light')]


def test_console_and_module_entrypoints():
    for command in (
        [str(Path(sys.executable).parent / 'ebible'), '--version'],
        [sys.executable, '-m', 'ebible', '--version'],
    ):
        result = subprocess.run(command, capture_output=True, encoding='utf-8', check=True)
        assert result.stdout.strip() == f'ebible {__version__}'


def test_optional_modules_and_textual_not_imported_by_core():
    code = """
import importlib
import sys
for module in ('models', 'refs', 'scripture', 'userdata', 'settings', 'plans', 'translate.base', 'translate.claude', 'translate.google', 'translate.service'):
    importlib.import_module('ebible.core.' + module)
assert 'textual' not in sys.modules
assert 'anthropic' not in sys.modules
from ebible.__main__ import main
try:
    main(['--version'])
except SystemExit as exc:
    assert exc.code == 0
assert 'textual' not in sys.modules
assert 'anthropic' not in sys.modules
"""
    subprocess.run([sys.executable, '-c', code], capture_output=True, encoding='utf-8', check=True)
