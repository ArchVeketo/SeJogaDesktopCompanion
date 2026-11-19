"""Leitor e amostrador puro de clipes externos de animação em glTF 2.0 (.gltf/.glb).

Converte trilhas glTF de rotação local (``STEP``, ``LINEAR`` e ``CUBICSPLINE``)
para deltas locais no referencial de autoria (``Rotation3(x=P, y=H, z=R)``)
compatíveis com ``LayerStack``, sem depender de Panda3D, Qt ou Win32.
"""

from __future__ import annotations

import base64
import json
import struct
from bisect import bisect_right
from dataclasses import dataclass, field
from functools import lru_cache
from math import acos, cos, sin, sqrt
from pathlib import Path
from typing import Any

from sejoga.nucleo.cinematica import (
    _GLTF_PARA_AUTORIA,
    _quat_para_mat3,
    hpr_de_matriz,
    mul,
    transposta,
)
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rotation3
from sejoga.nucleo.modelo import load_gltf_document
from sejoga.nucleo.recursos import assets_dir

Quat = tuple[float, float, float, float]

_GLB_MAGIC = b"glTF"
_GLB_BIN_CHUNK = 0x004E4942
_TIPO_CONTAGEM = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
_COMPONENTE_FMT = {
    5120: ("b", 1, True),
    5121: ("B", 1, True),
    5122: ("h", 2, True),
    5123: ("H", 2, True),
    5125: ("I", 4, False),
    5126: ("f", 4, False),
}
_GRUPOS_VALIDOS = frozenset(ALL_GROUPS)


@dataclass(frozen=True, slots=True)
class ContratoClipeGltf:
    """Metadados contratuais (sidecar JSON) associados a um clipe glTF."""

    id: str
    rig_revision: str
    origem: str
    autoria: str
    licenca: str
    duracao_s: float
    loop: bool = False
    modo_canal: str = "delta_local"
    interpolacao: tuple[str, ...] = ("LINEAR",)
    eventos: tuple[tuple[float, str], ...] = ()
    juntas_afetadas: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TrilhaRotacaoGltf:
    """Trilha de rotação de um grupo animável dentro de uma animação glTF."""

    grupo: str
    interpolacao: str
    tempos: tuple[float, ...]
    valores: tuple[Quat, ...]
    q_rest_inv: Quat = (0.0, 0.0, 0.0, 1.0)


@dataclass(frozen=True, slots=True)
class ClipeGltf:
    """Animação glTF pronta para amostragem em segundos."""

    nome: str
    duracao_s: float
    trilhas: tuple[TrilhaRotacaoGltf, ...]
    contrato: ContratoClipeGltf | None = None


@dataclass(frozen=True, slots=True)
class AmostraClipeGltf:
    """Resultado amostrado em um instante de reprodução."""

    ativa: bool = False
    delta_rig: dict[str, Rotation3] = field(default_factory=dict)
    eventos: tuple[str, ...] = ()


def _quat_norm(q: Quat) -> Quat:
    n = sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3])
    if n < 1e-8:
        return (0.0, 0.0, 0.0, 1.0)
    return (q[0] / n, q[1] / n, q[2] / n, q[3] / n)


def _quat_conj(q: Quat) -> Quat:
    return (-q[0], -q[1], -q[2], q[3])


def _quat_mul(a: Quat, b: Quat) -> Quat:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def _slerp_quat(q0: Quat, q1: Quat, u: float) -> Quat:
    a, b = _quat_norm(q0), _quat_norm(q1)
    dot = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
    if dot < 0.0:
        b = (-b[0], -b[1], -b[2], -b[3])
        dot = -dot
    if dot > 0.9995:
        return _quat_norm(tuple(a[i] + (b[i] - a[i]) * u for i in range(4)))  # type: ignore[return-value]
    theta_0 = acos(max(-1.0, min(1.0, dot)))
    theta = theta_0 * u
    sin_0 = sin(theta_0)
    s0 = cos(theta) - dot * sin(theta) / sin_0
    s1 = sin(theta) / sin_0
    return _quat_norm(tuple(s0 * a[i] + s1 * b[i] for i in range(4)))  # type: ignore[return-value]


def _cubicspline_quat(
    tri_0: tuple[Quat, Quat, Quat],
    tri_1: tuple[Quat, Quat, Quat],
    u: float,
    dt_seg: float,
) -> Quat:
    _, v0, b0 = tri_0
    a1, v1, _ = tri_1
    dot = v0[0] * v1[0] + v0[1] * v1[1] + v0[2] * v1[2] + v0[3] * v1[3]
    sinal = -1.0 if dot < 0.0 else 1.0
    u2 = u * u
    u3 = u2 * u
    h00 = 2.0 * u3 - 3.0 * u2 + 1.0
    h10 = (u3 - 2.0 * u2 + u) * dt_seg
    h01 = (-2.0 * u3 + 3.0 * u2) * sinal
    h11 = (u3 - u2) * dt_seg * sinal
    return _quat_norm(
        tuple(
            h00 * v0[i] + h10 * b0[i] + h01 * v1[i] + h11 * a1[i] for i in range(4)
        )  # type: ignore[arg-type]
    )


def _quat_gltf_para_rotation3(q: Quat) -> Rotation3:
    c = _GLTF_PARA_AUTORIA
    mat_autoria = mul(mul(c, _quat_para_mat3(_quat_norm(q))), transposta(c))
    h, p, r = hpr_de_matriz(mat_autoria)
    return Rotation3(x=p, y=h, z=r)


def _extrair_bin_glb(path: Path) -> bytes | None:
    raw = path.read_bytes()
    if raw[:4] != _GLB_MAGIC or len(raw) < 12:
        return None
    _, _, total = struct.unpack("<III", raw[:12])
    offset = 12
    while offset + 8 <= min(total, len(raw)):
        c_len, c_type = struct.unpack("<II", raw[offset : offset + 8])
        offset += 8
        if c_type == _GLB_BIN_CHUNK:
            return raw[offset : offset + c_len]
        offset += c_len
    return None


def _carregar_buffers(doc: dict[str, Any], base_dir: Path, glb_bin: bytes | None) -> list[bytes]:
    out: list[bytes] = []
    for idx, buf in enumerate(doc.get("buffers", [])):
        uri = buf.get("uri")
        if uri is None:
            out.append(glb_bin if idx == 0 and glb_bin is not None else b"")
        elif uri.startswith("data:"):
            _, payload = uri.split(",", 1)
            out.append(base64.b64decode(payload))
        else:
            out.append((base_dir / uri).read_bytes())
    return out


def _normalizar_valor(valor: float, ctype: int, normalizado: bool) -> float:
    if not normalizado or ctype == 5126:
        return float(valor)
    escalas = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}
    div = escalas.get(ctype, 1.0)
    return max(-1.0, float(valor) / div)


def _ler_accessor(
    doc: dict[str, Any], buffers: list[bytes], acc_idx: int
) -> list[tuple[float, ...]]:
    acc = doc["accessors"][acc_idx]
    bv = doc["bufferViews"][acc["bufferView"]]
    buf = buffers[bv.get("buffer", 0)]
    fmt_char, csize, pode_norm = _COMPONENTE_FMT[acc["componentType"]]
    ncomp = _TIPO_CONTAGEM[acc["type"]]
    norm = bool(acc.get("normalized", False)) and pode_norm
    stride = bv.get("byteStride") or (csize * ncomp)
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    fmt = "<" + fmt_char * ncomp
    rows: list[tuple[float, ...]] = []
    for i in range(acc["count"]):
        pos = base + i * stride
        bruto = struct.unpack_from(fmt, buf, pos)
        rows.append(tuple(_normalizar_valor(v, acc["componentType"], norm) for v in bruto))
    return rows


def _carregar_contrato(gltf_path: Path) -> ContratoClipeGltf | None:
    sidecar = gltf_path.with_suffix(".json")
    if not sidecar.is_file():
        return None
    dados = json.loads(sidecar.read_text(encoding="utf-8"))
    eventos = tuple((float(ev["t"]), str(ev["nome"])) for ev in dados.get("eventos", []))
    return ContratoClipeGltf(
        id=str(dados["id"]),
        rig_revision=str(dados.get("rig_revision", "mario.gltf@unknown")),
        origem=str(dados.get("origem", gltf_path.name)),
        autoria=str(dados.get("autoria", "desconhecido")),
        licenca=str(dados.get("licenca", "projeto")),
        duracao_s=float(dados.get("duracao_s", 0.0)),
        loop=bool(dados.get("loop", False)),
        modo_canal=str(dados.get("modo_canal", "delta_local")),
        interpolacao=tuple(dados.get("interpolacao", ["LINEAR"])),
        eventos=eventos,
        juntas_afetadas=tuple(dados.get("juntas_afetadas", [])),
    )


def _montar_trilha(
    doc: dict[str, Any],
    buffers: list[bytes],
    anim: dict[str, Any],
    ch: dict[str, Any],
    modo_canal: str,
) -> TrilhaRotacaoGltf | None:
    alvo = ch.get("target", {})
    if alvo.get("path") != "rotation" or "node" not in alvo:
        return None
    no = doc["nodes"][alvo["node"]]
    grupo = no.get("name", "")
    if grupo not in _GRUPOS_VALIDOS:
        return None
    samp = anim["samplers"][ch["sampler"]]
    interp = str(samp.get("interpolation", "LINEAR"))
    tempos = tuple(r[0] for r in _ler_accessor(doc, buffers, samp["input"]))
    vals_raw = _ler_accessor(doc, buffers, samp["output"])
    valores: tuple[Quat, ...] = tuple(
        (float(v[0]), float(v[1]), float(v[2]), float(v[3])) for v in vals_raw
    )
    q_rest = tuple(float(x) for x in no.get("rotation", (0.0, 0.0, 0.0, 1.0)))
    q_rest_inv = (
        (0.0, 0.0, 0.0, 1.0)
        if modo_canal == "delta_local"
        else _quat_conj(_quat_norm(q_rest))  # type: ignore[arg-type]
    )
    return TrilhaRotacaoGltf(
        grupo=grupo,
        interpolacao=interp,
        tempos=tempos,
        valores=valores,
        q_rest_inv=q_rest_inv,
    )


def carregar_clipe_gltf_arquivo(path: Path, *, nome: str | None = None) -> ClipeGltf | None:
    """Lê e valida um arquivo ``.gltf``/``.glb`` qualquer como ``ClipeGltf``."""
    if not path.is_file():
        return None
    doc = load_gltf_document(path)
    animacoes = doc.get("animations", [])
    if not animacoes:
        return None
    buffers = _carregar_buffers(doc, path.parent, _extrair_bin_glb(path))
    contrato = _carregar_contrato(path)
    modo_canal = contrato.modo_canal if contrato is not None else "delta_local"
    anim = animacoes[0]
    trilhas: list[TrilhaRotacaoGltf] = []
    for ch in anim.get("channels", []):
        trilha = _montar_trilha(doc, buffers, anim, ch, modo_canal)
        if trilha is not None:
            trilhas.append(trilha)
    if not trilhas:
        return None
    dur = max(max(t.tempos) for t in trilhas if t.tempos)
    if contrato is not None and contrato.duracao_s > 0.0:
        dur = contrato.duracao_s
    return ClipeGltf(
        nome=nome or path.stem,
        duracao_s=dur,
        trilhas=tuple(trilhas),
        contrato=contrato,
    )


@lru_cache(maxsize=16)
def carregar_clipe_gltf(nome: str) -> ClipeGltf | None:
    """Carrega um clipe glTF em ``assets/animation/<nome>.(glb|gltf)``."""
    raiz = assets_dir() / "animation"
    for sufixo in (".glb", ".gltf"):
        candidato = raiz / f"{nome}{sufixo}"
        if candidato.is_file():
            return carregar_clipe_gltf_arquivo(candidato, nome=nome)
    return None


def listar_clipes_gltf(subpasta: str = "piloto") -> tuple[str, ...]:
    """Lista nomes lógicos disponíveis na subpasta de clipes glTF."""
    pasta = assets_dir() / "animation" / subpasta
    if not pasta.is_dir():
        return ()
    nomes = {
        f"{subpasta}/{p.stem}"
        for p in sorted(pasta.iterdir())
        if p.suffix.lower() in (".gltf", ".glb")
    }
    return tuple(sorted(nomes))


def _amostrar_trilha(trilha: TrilhaRotacaoGltf, tempo: float) -> Rotation3:
    tempos = trilha.tempos
    valores = trilha.valores
    if not tempos or not valores:
        return Rotation3()
    if tempo <= tempos[0]:
        q_local = valores[1] if trilha.interpolacao == "CUBICSPLINE" else valores[0]
    elif tempo >= tempos[-1]:
        idx = (len(tempos) - 1) * 3 + 1 if trilha.interpolacao == "CUBICSPLINE" else len(tempos) - 1
        q_local = valores[idx]
    else:
        k = max(0, bisect_right(tempos, tempo) - 1)
        t0, t1 = tempos[k], tempos[k + 1]
        dt_seg = max(1e-6, t1 - t0)
        u = max(0.0, min(1.0, (tempo - t0) / dt_seg))
        if trilha.interpolacao == "STEP":
            q_local = valores[k]
        elif trilha.interpolacao == "CUBICSPLINE":
            i0, i1 = k * 3, (k + 1) * 3
            q_local = _cubicspline_quat(
                (valores[i0], valores[i0 + 1], valores[i0 + 2]),
                (valores[i1], valores[i1 + 1], valores[i1 + 2]),
                u,
                dt_seg,
            )
        else:
            q_local = _slerp_quat(valores[k], valores[k + 1], u)
    q_delta = _quat_mul(trilha.q_rest_inv, _quat_norm(q_local))
    return _quat_gltf_para_rotation3(q_delta)


def _resolver_parametros_gltf(
    clipe: ClipeGltf,
    override: dict[str, object],
) -> tuple[float, float, float, float, bool, tuple[tuple[float, str], ...]]:
    vel = max(0.05, float(override.get("velocidade", 1.0)))  # type: ignore[arg-type]
    inicio = max(0.0, float(override.get("inicio_s", 0.0)))  # type: ignore[arg-type]
    fim_raw = override.get("fim_s")
    fim = float(fim_raw) if fim_raw is not None else clipe.duracao_s  # type: ignore[arg-type]
    fim = max(inicio + 1e-3, min(clipe.duracao_s, fim))
    peso = max(0.0, min(1.0, float(override.get("peso_mistura", 1.0))))  # type: ignore[arg-type]
    loop = bool(
        override.get(
            "loop",
            clipe.contrato.loop if clipe.contrato is not None else False,
        )
    )
    eventos_cfg = override.get("eventos")
    lista_ev = (
        tuple((float(t_e), str(n_e)) for t_e, n_e in eventos_cfg)  # type: ignore[attr-defined]
        if eventos_cfg is not None
        else (clipe.contrato.eventos if clipe.contrato else ())
    )
    return vel, inicio, fim - inicio, peso, loop, lista_ev


def amostrar_clipe_gltf(
    nome: str,
    tempo: float,
    *,
    tempo_anterior: float | None = None,
) -> AmostraClipeGltf:
    """Amostra deltas e eventos contratuais de um clipe glTF no instante ``tempo``."""
    from sejoga.animacao.dados_autorais import clipes_gltf_ativos

    clipe = carregar_clipe_gltf(nome)
    if clipe is None or clipe.duracao_s <= 0.0:
        return AmostraClipeGltf()
    vel, inicio, trecho, peso, loop, lista_ev = _resolver_parametros_gltf(
        clipe, clipes_gltf_ativos().get(nome, {})
    )
    t_esc = tempo * vel
    t_rel = t_esc % trecho if loop else t_esc
    if not loop and (t_rel < 0.0 or t_rel >= trecho):
        return AmostraClipeGltf()
    t_eff = inicio + t_rel
    delta = {trilha.grupo: _amostrar_trilha(trilha, t_eff) for trilha in clipe.trilhas}
    if peso < 1.0 - 1e-6:
        delta = {
            g: Rotation3(r.x * peso, r.y * peso, r.z * peso)
            for g, r in delta.items()
        }
    eventos: list[str] = []
    if lista_ev and tempo_anterior is not None:
        t_prev_esc = tempo_anterior * vel
        t_prev = inicio + (t_prev_esc % trecho if loop else t_prev_esc)
        for t_ev, nome_ev in lista_ev:
            if t_prev < t_ev <= t_eff:
                eventos.append(nome_ev)
    return AmostraClipeGltf(ativa=True, delta_rig=delta, eventos=tuple(eventos))
