"""Testa o atualizador: release instalado, feed e download."""

import hashlib
import io
import json
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from sejoga.distribuicao import atualizador
from sejoga.distribuicao.atualizador import (
    ReleaseInfo,
    download_update,
    parse_manifest,
    version_order,
)


def manifest(channel="release", version="0.2.0", build_id=2):
    name = f"SeJogaCompanion-{channel}-{version}-windows-x64.zip"
    return dict(
        schema_version=1,
        architecture="windows-x64",
        channel=channel,
        version=version,
        build_id=build_id,
        version_order=version_order(version),
        name=name,
        size=16,
        sha256="a" * 64,
        url=f"https://github.com/{atualizador.REPOSITORY}/releases/download/updates-{channel}/{name}",
    )


@pytest.mark.parametrize(
    ("channel", "old", "new"),
    [
        ("release", "0.1.0", "0.2.0"),
        ("prerelease", "0.2.0rc1", "0.2.0rc2"),
        ("nightly", "0.2.0.dev20261104000000", "0.2.0.dev20261105000000"),
    ],
)
def test_channels_only_offer_newer_payloads(channel, old, new):
    current = ReleaseInfo(old, channel, 1)
    data = manifest(channel, new)
    update = parse_manifest(data, current)
    assert update.version == new
    assert update.name.endswith(".zip")
    assert parse_manifest(data, ReleaseInfo(new, channel, 2)) is None
    assert parse_manifest(manifest(channel, old), current) is None
    assert parse_manifest(manifest(channel, new, build_id=1), current) is None
    data["channel"] = next(c for c in atualizador.CHANNELS if c != channel)
    with pytest.raises(ValueError, match="incompatível"):
        parse_manifest(data, current)


@pytest.mark.parametrize(
    ("version", "channel"),
    [
        ("0.2.0rc1", "release"),
        ("0.2.0", "prerelease"),
        ("0.2.0", "nightly"),
        ("0.2.0.dev1", "prerelease"),
        ("0.2.0", "unknown"),
    ],
)
def test_bad_channel_version_combinations_fail(version, channel):
    with pytest.raises(ValueError):
        ReleaseInfo(version, channel)


def test_native_version_order_matches_supported_pep440_order():
    versions = [
        "0.2.0.dev20261105100000",
        "0.2.0a1",
        "0.2.0b1",
        "0.2.0rc1",
        "0.2.0rc2",
        "0.2.0",
        "0.3.0.dev20261105100000",
        "0.11.0",
    ]
    assert sorted(versions, key=version_order) == versions


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/ArchVeketo/SeJogaDesktopCompanion/releases/download/v1/a.zip",
        "https://example.com/a.zip",
        "https://github.com/other/project/releases/download/v1/a.zip",
        "https://github.com.evil.test/ArchVeketo/SeJogaDesktopCompanion/releases/download/v1/a.zip",
    ],
)
def test_external_or_insecure_download_urls_are_rejected(url):
    data = manifest()
    data["url"] = url
    with pytest.raises(ValueError):
        parse_manifest(data, ReleaseInfo("0.1.0", "release"))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("architecture", "other"),
        ("sha256", ""),
        ("size", 0),
        ("build_id", -1),
        ("version_order", [99, 99, 99, 3, 0]),
        ("schema_version", 999),
        ("name", "../../bad.zip"),
    ],
)
def test_invalid_manifest_fails_closed(key, value):
    data = manifest()
    data[key] = value
    with pytest.raises(ValueError):
        parse_manifest(data, ReleaseInfo("0.1.0", "release"))


def test_verified_package_download_is_atomic(tmp_path, monkeypatch):
    payload = b"PK-test-runtime!"
    data = manifest()
    data.update(size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    update = parse_manifest(data, ReleaseInfo("0.1.0", "release"))
    monkeypatch.setattr(atualizador, "_open", lambda _url: io.BytesIO(payload))
    path = download_update(update, tmp_path)
    assert path.read_bytes() == payload
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("payload", [b"PK-corrupt-data!", b"bad", b"a" * 100])
def test_corrupt_or_truncated_payload_is_not_promoted(tmp_path, monkeypatch, payload):
    data = manifest()
    data["sha256"] = hashlib.sha256(b"PK-test-runtime!").hexdigest()
    update = parse_manifest(data, ReleaseInfo("0.1.0", "release"))
    monkeypatch.setattr(atualizador, "_open", lambda _url: io.BytesIO(payload))
    with pytest.raises(ValueError):
        download_update(update, tmp_path)
    assert not list(tmp_path.iterdir())


def test_fixed_feed_does_not_need_new_installer_or_release_listing(monkeypatch):
    calls = []

    def read(url, limit):
        calls.append(url)
        return json.dumps(manifest()).encode()

    monkeypatch.setattr(atualizador, "_read", read)
    assert atualizador.check_update(ReleaseInfo("0.1.0", "release")).version == "0.2.0"
    assert calls == [
        f"https://github.com/{atualizador.REPOSITORY}/releases/download/updates-release/channel.json"
    ]


def test_unpublished_channel_is_not_an_error(monkeypatch):
    def missing(*args):
        raise HTTPError("test", 404, "missing", {}, None)

    monkeypatch.setattr(atualizador, "_read", missing)
    assert atualizador.check_update(ReleaseInfo("0.1.0", "release")) is None


def test_single_installer_runs_without_published_feed(monkeypatch):
    # Instalador unico: o runtime ja vem embutido, entao um feed 404 nao e fatal.
    # check_update apenas informa "sem atualizacao" (None). A logica equivalente do
    # launcher nativo (SeJogaLauncher.cs: FeedIndisponivel -> StartCurrent quando ha
    # runtime) e validada por inspecao, pois iscc/instalacao real nao rodam aqui.
    for channel in atualizador.CHANNELS:
        current = ReleaseInfo(
            "0.2.0"
            if channel == "release"
            else "0.2.0rc1"
            if channel == "prerelease"
            else "0.2.0.dev1",
            channel,
        )

        def missing(*args):
            raise HTTPError("feed", 404, "missing", {}, None)

        monkeypatch.setattr(atualizador, "_read", missing)
        assert atualizador.check_update(current) is None


def test_installed_channel_and_stable_launcher_are_found_outside_runtime(
    tmp_path, monkeypatch
):
    current = tmp_path / "runtime/current"
    current.mkdir(parents=True)
    monkeypatch.setattr(
        atualizador,
        "sys",
        SimpleNamespace(frozen=True, executable=str(current / "app.exe")),
    )
    (current / "release-info.json").write_text(
        json.dumps({"version": "0.2.0rc1", "channel": "prerelease", "build_id": 2})
    )
    assert atualizador.installed_release() == ReleaseInfo("0.2.0rc1", "prerelease", 2)
    launcher = tmp_path / "SeJogaLauncher.exe"
    launcher.write_bytes(b"fixture")
    assert atualizador.installed_launcher() == launcher
    from sejoga.configuracao import APP_NAME, profile_app_name

    # Instalador unico: o perfil mora sempre no mesmo caminho, independente do canal.
    assert profile_app_name() == APP_NAME
    (current / "release-info.json").write_text("invalid")
    assert atualizador.installed_release() is None


def test_config_channel_drives_update_feed(monkeypatch):
    # Dado o canal 'prerelease' na config, a checagem consulta o feed desse canal.
    calls = []

    def read(url, limit):
        calls.append(url)
        raise HTTPError("feed", 404, "missing", {}, None)

    monkeypatch.setattr(atualizador, "_read", read)
    from sejoga.configuracao import Settings

    settings = Settings()
    settings.update.channel = "prerelease"
    current = ReleaseInfo("0.1.0", "release")
    assert atualizador.check_update(current, channel=settings.update.channel) is None
    assert calls == [
        f"https://github.com/{atualizador.REPOSITORY}/releases/download/updates-prerelease/channel.json"
    ]


def test_troca_de_canal_compara_com_versao_e_build_instalados():
    instalado = ReleaseInfo("0.1.0", "release", 2)
    assert parse_manifest(
        manifest("nightly", "0.1.0.dev20261111000000", 3), instalado, channel="nightly"
    ) is None
    assert parse_manifest(
        manifest("nightly", "0.2.0.dev20261111000000", 1), instalado, channel="nightly"
    ) is None
    assert parse_manifest(
        manifest("nightly", "0.2.0.dev20261111000000", 3), instalado, channel="nightly"
    ).channel == "nightly"


def test_external_redirect_is_blocked_before_following():
    redirect = atualizador._GitHubRedirect()
    for url in ("http://github.com/file", "https://example.com/file"):
        with pytest.raises(ValueError, match="Redirecionamento"):
            redirect.redirect_request(None, None, 302, "", {}, url)
