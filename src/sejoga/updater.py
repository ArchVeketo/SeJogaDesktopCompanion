"""Public GitHub release channels and verified installer downloads (no engine)."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from packaging.version import Version

REPOSITORY = 'ArchVeketo/SeJogaDesktopCompanion'
CHANNELS = ('release', 'prerelease', 'nightly')
MAX_INSTALLER_BYTES = 1024 * 1024 * 1024
MAX_API_BYTES = 4 * 1024 * 1024
ALLOWED_HOSTS = frozenset({'api.github.com', 'github.com',
                           'release-assets.githubusercontent.com', 'objects.githubusercontent.com'})


class _GitHubRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != 'https' or parsed.hostname not in ALLOWED_HOSTS:
            raise ValueError('Redirecionamento de download inválido.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    channel: str
    build_id: int = 0

    def __post_init__(self) -> None:
        version = Version(self.version)
        object.__setattr__(self, 'version', str(version))
        if self.channel not in CHANNELS:
            raise ValueError('Canal de atualização inválido.')
        if self.channel == 'release' and version.is_prerelease:
            raise ValueError('Release estável não pode ter versão de desenvolvimento.')
        if self.channel == 'prerelease' and (not version.is_prerelease or version.is_devrelease):
            raise ValueError('Pré-release requer versão alpha, beta ou rc.')
        if self.channel == 'nightly' and not version.is_devrelease:
            raise ValueError('Nightly requer versão .dev com identificador crescente.')


def installed_release() -> ReleaseInfo | None:
    if not getattr(sys, 'frozen', False):
        return None
    path = Path(sys.executable).parent / 'release-info.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        return ReleaseInfo(version=data['version'], channel=data['channel'], build_id=int(data.get('build_id', 0)))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _asset_url(url: str) -> str:
    parsed = urlsplit(url)
    prefix = f'/{REPOSITORY}/releases/download/'
    if (parsed.scheme != 'https' or parsed.netloc.lower() != 'github.com'
            or not parsed.path.startswith(prefix) or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise ValueError('Download fora das releases oficiais do SeJoga.')
    return url


def _open(url: str):
    request = Request(url, headers={
        'User-Agent': 'SeJogaDesktopCompanion-Updater',
        'Accept': 'application/vnd.github+json' if url.startswith('https://api.github.com/') else '*/*',
    })
    response = build_opener(_GitHubRedirect()).open(request, timeout=20)
    # GitHub redirects release assets to its own signed CDN URLs.
    final = urlsplit(response.geturl())
    if final.scheme != 'https' or final.hostname not in ALLOWED_HOSTS:
        response.close()
        raise ValueError('Redirecionamento de download inválido.')
    return response


def _read(url: str, limit: int) -> bytes:
    with _open(url) as response:
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ValueError('Resposta de atualização excede o tamanho permitido.')
    return content


@dataclass(frozen=True)
class Update:
    version: str
    channel: str
    name: str
    url: str
    sha256: str
    size: int
    build_id: int


def version_order(version: str) -> list[int]:
    parsed = Version(version)
    if (len(parsed.release) != 3 or parsed.epoch or parsed.local or parsed.post is not None
            or (parsed.dev is not None and parsed.pre is not None)):
        raise ValueError('Use major.minor.patch, a/b/rc ou .dev para versões públicas.')
    rank = -1 if parsed.is_devrelease else {'a': 0, 'b': 1, 'rc': 2}[parsed.pre[0]] if parsed.pre else 3
    serial = (parsed.dev or 0) if parsed.is_devrelease else parsed.pre[1] if parsed.pre else 0
    return [*parsed.release, rank, serial]


def parse_manifest(data: dict, current: ReleaseInfo) -> Update | None:
    if (data.get('schema_version') != 1 or data.get('architecture') != 'windows-x64'
            or data.get('channel') != current.channel):
        raise ValueError('Manifesto incompatível com este canal/plataforma.')
    candidate = ReleaseInfo(data['version'], data['channel'], int(data['build_id']))
    if candidate.build_id <= 0:
        raise ValueError('Identificador de build inválido.')
    if data.get('version_order') != version_order(candidate.version):
        raise ValueError('Ordem de versão inválida no manifesto.')
    name = f'SeJogaCompanion-{candidate.channel}-{candidate.version}-windows-x64.zip'
    url = _asset_url(data['url'])
    if data.get('name') != name or not urlsplit(url).path.endswith('/'+name):
        raise ValueError('Pacote de atualização inválido.')
    digest = data['sha256']
    size = int(data['size'])
    if not re.fullmatch('[0-9a-f]{64}', digest) or not 0 < size <= MAX_INSTALLER_BYTES:
        raise ValueError('Integridade/tamanho do pacote inválidos.')
    if Version(candidate.version) <= Version(current.version) or candidate.build_id <= current.build_id:
        return None
    return Update(candidate.version, candidate.channel, name, url, digest, size, candidate.build_id)


def check_update(current: ReleaseInfo) -> Update | None:
    from urllib.error import HTTPError
    url = f'https://github.com/{REPOSITORY}/releases/download/updates-{current.channel}/channel.json'
    try:
        data = json.loads(_read(url, MAX_API_BYTES))
    except HTTPError as error:
        if error.code == 404:
            return None
        raise
    return parse_manifest(data, current)


# Versão base do pacote (pyproject); usada como piso quando não estamos "frozen".
BASE_VERSION = '0.1.0'
# Versões-piso válidas por canal para montar a checagem a partir da config.
# ReleaseInfo valida canal x versão, então cada canal precisa de uma versão compatível.
_VERSAO_PISO_POR_CANAL = {
    'release': BASE_VERSION,
    'prerelease': f'{BASE_VERSION}a1',
    'nightly': f'{BASE_VERSION}.dev1',
}


def release_para_checagem(channel: str) -> ReleaseInfo:
    """Monta o ReleaseInfo de checagem a partir do canal escolhido na config.

    Quando "frozen", usa o release instalado (versão/build_id reais) se ele
    pertencer ao canal pedido; caso contrário parte da versão-piso do canal,
    de modo que qualquer build publicado no feed seja considerado mais novo.
    """
    if channel not in CHANNELS:
        raise ValueError('Canal de atualização inválido.')
    instalado = installed_release()
    if instalado is not None and instalado.channel == channel:
        return instalado
    return ReleaseInfo(version=_VERSAO_PISO_POR_CANAL[channel], channel=channel, build_id=0)


def reescrever_canal_channel_info(path: Path, channel: str) -> bool:
    """Reescreve atomicamente o campo ``channel`` de um ``channel-info.json``.

    Mantém os demais campos (``scope`` etc.). Guard clause: se o arquivo não
    existir (execução em modo fonte/dev), não falha e retorna ``False``.
    """
    if channel not in CHANNELS:
        raise ValueError('Canal de atualização inválido.')
    if not path.is_file():
        return False
    dados = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(dados, dict):
        raise ValueError('channel-info.json inválido.')
    dados['channel'] = channel
    conteudo = json.dumps(dados, ensure_ascii=False)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix='channel-info-', suffix='.tmp', delete=False) as stream:
        temporario = Path(stream.name)
        stream.write(conteudo)
    try:
        temporario.replace(path)
    finally:
        temporario.unlink(missing_ok=True)
    return True


def installed_launcher() -> Path | None:
    if not getattr(sys, 'frozen', False):
        return None
    current = Path(sys.executable).parent
    if current.name != 'current' or current.parent.name != 'runtime':
        return None
    path = current.parent.parent/'SeJogaLauncher.exe'
    return path if path.is_file() else None


def download_update(update: Update, cache_dir: Path) -> Path:
    """Download a runtime package; the privileged agent independently rechecks it."""
    _asset_url(update.url)
    if Path(update.name).name != update.name or not re.fullmatch(
        r'SeJogaCompanion-(release|prerelease|nightly)-[a-zA-Z0-9.+-]+-windows-x64\.zip', update.name
    ):
        raise ValueError('Nome de pacote inválido.')
    digest = update.sha256
    if not digest or not re.fullmatch('[0-9a-fA-F]{64}', digest):
        raise ValueError('Checksum SHA256 indisponível.')
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / update.name
    sha = hashlib.sha256()
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=cache_dir, suffix='.part', delete=False) as output:
            temporary = Path(output.name)
            with _open(update.url) as response:
                size = 0
                while chunk := response.read(256 * 1024):
                    size += len(chunk)
                    if size > update.size or size > MAX_INSTALLER_BYTES:
                        raise ValueError('Tamanho inesperado do instalador.')
                    sha.update(chunk)
                    output.write(chunk)
        if size != update.size or sha.hexdigest() != digest.lower():
            raise ValueError('Download incompleto ou SHA256 inválido; atualização cancelada.')
        temporary.replace(destination)
        return destination
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
