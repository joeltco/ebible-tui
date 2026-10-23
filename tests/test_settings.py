import json
from dataclasses import replace

import pytest

from ebible.core.settings import Settings, load_settings, save_settings
from ebible.paths import config_dir, data_dir, settings_path, user_db_path


def test_paths_resolved_each_call(tmp_path, monkeypatch):
    assert config_dir() == tmp_path / 'config' / 'ebible'
    assert data_dir() == tmp_path / 'data' / 'ebible'
    assert not config_dir().exists() and not data_dir().exists()
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'changed'))
    assert settings_path() == tmp_path / 'changed' / 'ebible' / 'settings.json'
    assert user_db_path() == data_dir() / 'user.db'
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('XDG_CONFIG_HOME', 'relative')
    monkeypatch.setenv('XDG_DATA_HOME', '')
    assert config_dir() == tmp_path / '.config' / 'ebible'
    assert data_dir() == tmp_path / '.local' / 'share' / 'ebible'
    monkeypatch.delenv('XDG_CONFIG_HOME')
    assert config_dir() == tmp_path / '.config' / 'ebible'


def test_missing_and_roundtrip():
    assert load_settings() == Settings()
    value = Settings(
        theme='parchment',
        verse_flow='paragraph',
        verse_numbers=False,
        verse_spacing='compact',
        book_name_language='am',
        text_max_width=80,
        translation_backend='off',
        haptic_feedback=True,
    )
    save_settings(value)
    assert load_settings() == value
    assert json.loads(settings_path().read_text(encoding='utf-8'))['theme'] == 'parchment'


@pytest.mark.parametrize('payload', ['{', '[]', 'null', '42', '"text"'])
def test_corrupt_json(tmp_path, payload):
    path = tmp_path / 'fixture.json'
    path.write_text(payload, encoding='utf-8')
    assert load_settings(path) == Settings()


def test_invalid_utf8(tmp_path):
    path = tmp_path / 'fixture.json'
    path.write_bytes(b'\xff')
    assert load_settings(path) == Settings()


@pytest.mark.parametrize(
    ('key', 'value'),
    [
        ('theme', ''),
        ('theme', 1),
        ('theme', 'x' * 101),
        ('layout', 'bad'),
        ('verse_flow', 'bad'),
        ('verse_numbers', 'yes'),
        ('verse_spacing', None),
        ('book_name_language', 'fr'),
        ('text_max_width', True),
        ('text_max_width', 19),
        ('text_max_width', 241),
        ('translation_backend', 'bad'),
        ('haptic_feedback', 1),
        ('show_untranslated_placeholder', []),
    ],
)
def test_invalid_fields_default_independently(tmp_path, key, value):
    path = tmp_path / 'fixture.json'
    path.write_text(json.dumps({key: value, 'unknown': 42}), encoding='utf-8')
    assert load_settings(path) == Settings()


def test_valid_keys_survive_invalid_keys(tmp_path):
    path = tmp_path / 'fixture.json'
    path.write_text(
        '{"layout":"english","theme":"parchment","text_max_width":0,"unknown":true,"show_untranslated_placeholder":true}',
        encoding='utf-8',
    )
    assert load_settings(path) == replace(Settings(), theme='parchment')


def test_atomic_failure_preserves_old_file(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    save_settings(Settings(), path)

    def fail(source, target):
        assert source.parent == target.parent
        raise OSError('fixture: failed replace')

    monkeypatch.setattr('ebible.core.settings.os.replace', fail)
    with pytest.raises(OSError):
        save_settings(Settings(theme='parchment'), path)
    assert load_settings(path) == Settings()
    assert list(tmp_path.iterdir()) == [path]


def test_invalid_save_rejected(tmp_path):
    with pytest.raises(ValueError):
        save_settings(Settings(text_max_width=0), tmp_path / 'bad.json')
    assert not (tmp_path / 'bad.json').exists()
