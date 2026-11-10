import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

from sejoga.distribuicao.atualizador import ReleaseInfo, parse_manifest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_update_test', ROOT/'tools/construir_atualizacao.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_package_contains_runtime_metadata_and_never_developer_profiles(tmp_path):
    bundle = tmp_path/'bundle'
    (bundle/'_internal').mkdir(parents=True)
    (bundle/'SeJogaCompanion.exe').write_bytes(b'fixture-not-executed')
    (bundle/'_internal/data.bin').write_bytes(b'runtime')
    (bundle/'USER-DATA').mkdir()
    (bundle/'USER-DATA/secret.toml').write_text('must not ship')
    (bundle/'_internal/source.blend').write_bytes(b'art-source')
    result = builder.build_package(bundle, tmp_path/'output', ReleaseInfo('0.2.0', 'release', 2))
    archive = tmp_path/'output'/result['name']
    assert result['sha256'] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert result['size'] == archive.stat().st_size
    with zipfile.ZipFile(archive) as data:
        names = data.namelist()
        assert 'SeJogaCompanion.exe' in names and '_internal/data.bin' in names
        assert not any('user-data' in n.lower() or n.endswith('.blend') for n in names)
        info = json.loads(data.read('release-info.json'))
        assert info['build_id'] == 2 and info['version'] == '0.2.0'
    assert parse_manifest(result, ReleaseInfo('0.1.0', 'release', 1)).name == archive.name
