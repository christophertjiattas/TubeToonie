from __future__ import annotations

import sys
import types

import pytest

from ytaudio_secrets import TonieCredentials, get_tonie_credentials
from ytaudio_tonie import resolve_tonie_credentials
from ytaudio_youtube import normalize_youtube_url


def test_normalize_youtube_url_watch_strips_playlist_params():
    url = "https://www.youtube.com/watch?v=hcu8qlRRVPE&list=RDhcu8qlRRVPE&start_radio=1"
    assert normalize_youtube_url(url) == "https://www.youtube.com/watch?v=hcu8qlRRVPE"


def test_normalize_youtube_url_youtu_be():
    url = "https://youtu.be/hcu8qlRRVPE?t=10"
    assert normalize_youtube_url(url) == "https://www.youtube.com/watch?v=hcu8qlRRVPE"


def test_get_tonie_credentials_env_over_keyring(monkeypatch: pytest.MonkeyPatch):
    # Even if keyring returns something, env should win.
    monkeypatch.setenv("TONIE_USERNAME", "env@example.com")
    monkeypatch.setenv("TONIE_PASSWORD", "envpw")

    fake_keyring = types.SimpleNamespace(
        get_password=lambda service, key: "keyring-value",
    )

    # Force supported OS
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)

    creds = get_tonie_credentials()
    assert creds is not None
    assert creds.username == "env@example.com"
    assert creds.password == "envpw"


def test_get_tonie_credentials_keyring_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TONIE_USERNAME", raising=False)
    monkeypatch.delenv("TONIE_PASSWORD", raising=False)

    store = {
        ("tubetoonie", "tonie_username"): "key@example.com",
        ("tubetoonie", "tonie_password"): "keypw",
    }

    def fake_get_password(service: str, key: str):
        return store.get((service, key))

    fake_keyring = types.SimpleNamespace(get_password=fake_get_password)

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)

    creds = get_tonie_credentials()
    assert creds is not None
    assert creds.username == "key@example.com"
    assert creds.password == "keypw"


def test_resolve_tonie_credentials_priority_explicit_over_everything(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TONIE_USERNAME", "env@example.com")
    monkeypatch.setenv("TONIE_PASSWORD", "envpw")

    resolved = resolve_tonie_credentials(username="explicit@example.com", password="explicitpw")
    assert resolved is not None
    assert resolved.username == "explicit@example.com"
    assert resolved.password == "explicitpw"
