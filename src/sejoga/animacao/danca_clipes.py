"""Carregador e amostrador 1:1 de clipes de dança extraídos dos emotes (.blend).

Os arquivos JSON em ``assets/animation/loops/<estilo>.json`` contêm quadros de
retargeting 3D 1:1 (intro + loop) para o rig do Mário e para ``LegPose``, sem
dependência de Blender, Panda3D, Qt ou Win32 em tempo de execução.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from functools import lru_cache

from sejoga.animacao.dados_autorais import danca_ativa
from sejoga.nucleo.esqueleto import Rotation3
from sejoga.nucleo.recursos import assets_dir


@dataclass(frozen=True, slots=True)
class ClipeEmote:
    """Clipe de emote com introdução opcional (tocada 1x) e frase principal em loop."""

    estilo: str
    fps: float
    quadros_intro: tuple[dict[str, Rotation3], ...]
    quadros_pernas_intro: tuple[dict[str, float], ...]
    raiz_intro: tuple[tuple[float, float], ...]
    quadros: tuple[dict[str, Rotation3], ...]
    quadros_pernas: tuple[dict[str, float], ...]
    raiz: tuple[tuple[float, float], ...]
    velocidade: float = 1.0
    bpm_nativo: float = 108.0
    quat_intro: tuple[tuple[float, float, float, float], ...] = ()
    quat_raiz: tuple[tuple[float, float, float, float], ...] = ()
    em_loop: bool = True
    dedos_intro: tuple[tuple[tuple[float, ...], tuple[float, ...]], ...] = ()
    dedos: tuple[tuple[tuple[float, ...], tuple[float, ...]], ...] = ()
    inicio_s: float = 0.0
    fim_s: float | None = None
    peso_mistura: float = 1.0
    deslocamento_intro: tuple[tuple[float, float], ...] = ()
    deslocamento: tuple[tuple[float, float], ...] = ()

    @property
    def intro(self) -> tuple[dict[str, Rotation3], ...]:
        """Quadros da introdução (tocada uma vez)."""
        return self.quadros_intro

    @property
    def loop(self) -> tuple[dict[str, Rotation3], ...]:
        """Quadros do loop contínuo (repetidos se menor que 60 quadros)."""
        if len(self.quadros) >= 60 or not self.quadros:
            return self.quadros
        rep = (60 + len(self.quadros) - 1) // len(self.quadros)
        return self.quadros * rep


def _parse_quadros_rig(
    brutos: list[dict[str, list[float]]],
) -> tuple[dict[str, Rotation3], ...]:
    lista: list[dict[str, Rotation3]] = []
    for q in brutos:
        pose: dict[str, Rotation3] = {}
        for grupo, valores in q.items():
            if isinstance(valores, list) and len(valores) == 3:
                pose[grupo] = Rotation3(
                    float(valores[0]),
                    float(valores[1]),
                    float(valores[2]),
                )
        lista.append(pose)
    return tuple(lista)


def _parse_quadros_pernas(
    brutos: list[dict[str, float]],
    n_fallback: int,
) -> tuple[dict[str, float], ...]:
    lista: list[dict[str, float]] = []
    for qp in brutos:
        if isinstance(qp, dict):
            lista.append({str(k): float(v) for k, v in qp.items()})
    while len(lista) < n_fallback:
        lista.append({})
    return tuple(lista)


def _parse_raiz(
    brutos: list[list[float]],
    n_fallback: int,
) -> tuple[tuple[float, float], ...]:
    lista: list[tuple[float, float]] = []
    for r in brutos:
        if isinstance(r, list) and len(r) >= 2:
            lista.append((float(r[0]), float(r[1])))
    while len(lista) < n_fallback:
        lista.append((0.0, 0.0))
    return tuple(lista)


def _parse_quat_raiz(
    brutos: list[list[float]],
    n_fallback: int,
) -> tuple[tuple[float, float, float, float], ...]:
    import math

    if not any(isinstance(r, list) and len(r) >= 6 for r in brutos):
        return ()
    lista: list[tuple[float, float, float, float]] = []
    for r in brutos:
        if isinstance(r, list) and len(r) >= 6:
            w, x, y, z = float(r[2]), float(r[3]), float(r[4]), float(r[5])
            n = math.sqrt(w * w + x * x + y * y + z * z)
            if n > 1e-9:
                lista.append((w / n, x / n, y / n, z / n))
            else:
                lista.append((1.0, 0.0, 0.0, 0.0))
        elif isinstance(r, list) and len(r) >= 2:
            meio = math.radians(float(r[1])) * 0.5
            lista.append((math.cos(meio), 0.0, 0.0, math.sin(meio)))
        else:
            lista.append((1.0, 0.0, 0.0, 0.0))
    while len(lista) < n_fallback:
        lista.append((1.0, 0.0, 0.0, 0.0))
    return tuple(lista)


def _parse_dedos(
    brutos: object,
    esperado: int,
) -> tuple[tuple[tuple[float, ...], tuple[float, ...]], ...]:
    if not isinstance(brutos, list) or esperado <= 0:
        return ()
    saida: list[tuple[tuple[float, ...], tuple[float, ...]]] = []
    for item in brutos[:esperado]:
        if not isinstance(item, dict):
            saida.append(((0.0,) * 5, (0.0,) * 5))
            continue
        r_raw = item.get("right", ())
        l_raw = item.get("left", ())
        r_vals = tuple(float(r_raw[i]) if i < len(r_raw) else 0.0 for i in range(5))
        l_vals = tuple(float(l_raw[i]) if i < len(l_raw) else 0.0 for i in range(5))
        saida.append((r_vals, l_vals))
    if not saida:
        return ()
    ultimo = saida[-1]
    while len(saida) < esperado:
        saida.append(ultimo)
    return tuple(saida)


@lru_cache(maxsize=64)
def _carregar_clipe_em(pasta_sub: str, estilo: str) -> ClipeEmote | None:
    caminho = assets_dir() / "animation" / pasta_sub / f"{estilo}.json"
    if not caminho.exists():
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        fps = float(dados.get("fps", 24.0))
        q_intro = _parse_quadros_rig(dados.get("quadros_intro", []))
        p_intro = _parse_quadros_pernas(dados.get("quadros_pernas_intro", []), len(q_intro))
        r_intro = _parse_raiz(dados.get("raiz_intro", []), len(q_intro))
        rq_intro = _parse_quat_raiz(dados.get("raiz_intro", []), len(q_intro))
        d_intro = _parse_dedos(dados.get("dedos_intro", []), len(q_intro))

        q_loop = _parse_quadros_rig(dados.get("quadros", []))
        if not q_loop:
            return None
        p_loop = _parse_quadros_pernas(dados.get("quadros_pernas", []), len(q_loop))
        r_loop = _parse_raiz(dados.get("raiz", []), len(q_loop))
        rq_loop = _parse_quat_raiz(dados.get("raiz", []), len(q_loop))
        d_loop = _parse_dedos(dados.get("dedos", []), len(q_loop))
        velocidade = max(0.35, min(2.2, float(dados.get("velocidade", 1.0))))
        bpm_nativo = max(55.0, min(200.0, float(dados.get("bpm_nativo", 108.0))))

        return ClipeEmote(
            estilo=estilo,
            fps=max(1.0, fps),
            quadros_intro=q_intro,
            quadros_pernas_intro=p_intro,
            raiz_intro=r_intro,
            quadros=q_loop,
            quadros_pernas=p_loop,
            raiz=r_loop,
            velocidade=velocidade,
            bpm_nativo=bpm_nativo,
            quat_intro=rq_intro,
            quat_raiz=rq_loop,
            deslocamento_intro=_parse_raiz(dados.get("deslocamento_intro", []), len(q_intro)),
            deslocamento=_parse_raiz(dados.get("deslocamento", []), len(q_loop)),
            em_loop=bool(dados.get("loop", True)),
            dedos_intro=d_intro,
            dedos=d_loop,
        )
    except Exception:
        return None


def carregar_clipe_emote(estilo: str) -> ClipeEmote | None:
    """Carrega o clipe de loop de ``assets/animation/loops/<estilo>.json`` se existir."""
    clipe = _carregar_clipe_em("loops", estilo)
    if clipe is None:
        return None
    override = danca_ativa().get("clipes", {}).get(estilo)
    if not isinstance(override, dict):
        return clipe
    return replace(
        clipe,
        velocidade=float(override.get("velocidade", clipe.velocidade)),
        bpm_nativo=float(override.get("bpm", clipe.bpm_nativo)),
        em_loop=bool(override.get("loop", clipe.em_loop)),
        inicio_s=max(0.0, float(override.get("inicio_s", 0.0))),
        fim_s=(
            float(override["fim_s"])
            if override.get("fim_s") is not None
            else None
        ),
        peso_mistura=max(0.0, min(1.0, float(override.get("peso_mistura", 1.0)))),
    )


def _suavizar_clipe_acao(
    quadros: tuple[dict[str, Rotation3], ...],
    *,
    em_loop: bool,
) -> tuple[dict[str, Rotation3], ...]:
    """Suaviza flips de gimbal em punhos e eventuais degraus na emenda do loop."""
    n = len(quadros)
    if n < 5:
        return quadros
    buf = [dict(q) for q in quadros]
    zero = Rotation3()

    def _picos(grupo: str, limiar: float) -> set[int]:
        indices: set[int] = set()
        fim = n if em_loop else n - 1
        for i in range(fim):
            j = (i + 1) % n
            ra = buf[i].get(grupo, zero)
            rb = buf[j].get(grupo, zero)
            d = max(
                abs(((rb.x - ra.x + math.pi) % math.tau) - math.pi),
                abs(((rb.y - ra.y + math.pi) % math.tau) - math.pi),
                abs(((rb.z - ra.z + math.pi) % math.tau) - math.pi),
            )
            if d > limiar:
                for off in (-2, -1, 0, 1, 2):
                    idx = i + off
                    if em_loop:
                        indices.add(idx % n)
                    elif 1 <= idx <= n - 2:
                        indices.add(idx)
        return indices

    def _suavizar_indices(grupo: str, indices: set[int], passagens: int) -> None:
        if not indices:
            return
        for _ in range(passagens):
            proximo = [q.get(grupo, zero) for q in buf]
            for idx in indices:
                ant = buf[(idx - 1) % n].get(grupo, zero)
                cur = buf[idx].get(grupo, zero)
                seg = buf[(idx + 1) % n].get(grupo, zero)
                # Média local usando menor arco a partir do quadro atual
                dx = ((((ant.x - cur.x + math.pi) % math.tau) - math.pi)
                      + (((seg.x - cur.x + math.pi) % math.tau) - math.pi)) * 0.25
                dy = ((((ant.y - cur.y + math.pi) % math.tau) - math.pi)
                      + (((seg.y - cur.y + math.pi) % math.tau) - math.pi)) * 0.25
                dz = ((((ant.z - cur.z + math.pi) % math.tau) - math.pi)
                      + (((seg.z - cur.z + math.pi) % math.tau) - math.pi)) * 0.25
                proximo[idx] = Rotation3(cur.x + dx, cur.y + dy, cur.z + dz)
            for idx in indices:
                if grupo in buf[idx]:
                    buf[idx][grupo] = proximo[idx]

    # Filtra flips bruscos de punho (±0.95 rad gimbal flip no Mixamo arm_stretching)
    for grupo in ("hand", "hand2"):
        _suavizar_indices(grupo, _picos(grupo, 0.24), 12)

    # Em clipes cíclicos curtos (ex.: run_mixamo), suaviza eventual quina perto da emenda.
    if em_loop:
        todos = set().union(*(q.keys() for q in buf))
        for grupo in todos:
            pares = ((-2, -1), (-1, 0), (0, 1))
            max_borda = 0.0
            for ia, ib in pares:
                ra = buf[ia % n].get(grupo, zero)
                rb = buf[ib % n].get(grupo, zero)
                d_borda = max(
                    abs(((rb.x - ra.x + math.pi) % math.tau) - math.pi),
                    abs(((rb.y - ra.y + math.pi) % math.tau) - math.pi),
                    abs(((rb.z - ra.z + math.pi) % math.tau) - math.pi),
                )
                max_borda = max(max_borda, d_borda)
            if max_borda > 0.28:
                emenda_idx = {idx % n for idx in (-3, -2, -1, 0, 1, 2)}
                _suavizar_indices(grupo, emenda_idx, 5)

    return tuple(buf)


def carregar_clipe_acao(nome: str) -> ClipeEmote | None:
    """Carrega um clipe de ação/locomoção em ``assets/animation/acoes/<nome>.json``."""
    clipe = _carregar_clipe_em("acoes", nome)
    if clipe is None:
        return None
    suav = _suavizar_clipe_acao(clipe.quadros, em_loop=clipe.em_loop)
    if suav is clipe.quadros:
        return clipe
    return replace(clipe, quadros=suav)


def _lerp_ang(a: float, b: float, u: float) -> float:
    """Interpola ângulos em radianos pelo menor arco."""
    return a + (((b - a + math.pi) % math.tau) - math.pi) * u


def _interpolar_pose(
    a: dict[str, Rotation3], b: dict[str, Rotation3], u: float
) -> dict[str, Rotation3]:
    chaves = set(a.keys()) | set(b.keys())
    zero = Rotation3()
    saida: dict[str, Rotation3] = {}
    for k in chaves:
        ra = a.get(k, zero)
        rb = b.get(k, zero)
        saida[k] = Rotation3(
            _lerp_ang(ra.x, rb.x, u),
            _lerp_ang(ra.y, rb.y, u),
            _lerp_ang(ra.z, rb.z, u),
        )
    return saida


def _interpolar_pernas(
    a: dict[str, float], b: dict[str, float], u: float
) -> dict[str, float]:
    chaves = set(a.keys()) | set(b.keys())
    return {
        k: a.get(k, 0.0) + (b.get(k, 0.0) - a.get(k, 0.0)) * u
        for k in chaves
    }


def _tempo_com_recorte(tempo_segundos: float, clipe: ClipeEmote) -> float:
    inicio = max(0.0, clipe.inicio_s)
    if clipe.fim_s is not None and clipe.fim_s > inicio:
        trecho = clipe.fim_s - inicio
        return inicio + (
            (tempo_segundos % trecho) if clipe.em_loop else min(trecho, max(0.0, tempo_segundos))
        )
    return max(0.0, tempo_segundos) + inicio


def _indice_e_fracao(
    tempo_segundos: float,
    clipe: ClipeEmote,
) -> tuple[
    tuple[dict[str, Rotation3], ...],
    tuple[dict[str, float], ...],
    tuple[tuple[float, float], ...],
    int,
    int,
    float,
]:
    """Resolve se o instante atual está na introdução (1x) ou no loop contínuo."""
    t_quadros = max(0.0, _tempo_com_recorte(tempo_segundos, clipe)) * clipe.fps
    n_intro = len(clipe.quadros_intro)
    if n_intro > 0 and t_quadros < n_intro:
        idx0 = min(n_intro - 1, int(t_quadros))
        frac = t_quadros - idx0
        if idx0 + 1 < n_intro:
            return (
                clipe.quadros_intro,
                clipe.quadros_pernas_intro,
                clipe.raiz_intro,
                idx0,
                idx0 + 1,
                frac,
            )
        # Transição do último quadro da intro para o quadro 0 do loop
        return (
            (*clipe.quadros_intro, clipe.quadros[0]),
            (*clipe.quadros_pernas_intro, clipe.quadros_pernas[0]),
            (*clipe.raiz_intro, clipe.raiz[0]),
            idx0,
            idx0 + 1,
            frac,
        )

    n_loop = len(clipe.quadros)
    if not clipe.em_loop:
        pos = min(float(n_loop - 1), max(0.0, t_quadros - n_intro))
        idx0 = min(n_loop - 1, int(pos))
        idx1 = min(n_loop - 1, idx0 + 1)
        frac = pos - int(pos)
    else:
        pos_loop = (t_quadros - n_intro) % n_loop
        idx0 = int(pos_loop) % n_loop
        idx1 = (idx0 + 1) % n_loop
        frac = pos_loop - int(pos_loop)
    return (
        clipe.quadros,
        clipe.quadros_pernas,
        clipe.raiz,
        idx0,
        idx1,
        frac,
    )


def _ajustar_celebration_dance(pose: dict[str, Rotation3]) -> None:
    """Abre os braços para fora do visor e orienta as palmas para a câmera (-Y)."""
    ra, la = pose.get("right-arm"), pose.get("left-arm")
    if ra is not None:
        pose["right-arm"] = Rotation3(
            ra.x - math.radians(12.0), ra.y - math.radians(56.0), ra.z - math.radians(14.0)
        )
    if la is not None:
        pose["left-arm"] = Rotation3(
            la.x - math.radians(12.0), la.y + math.radians(56.0), la.z + math.radians(14.0)
        )
    for ant in ("ant-arm", "ant-arm2"):
        ar = pose.get(ant)
        if ar is not None:
            pose[ant] = Rotation3(ar.x, ar.y, ar.z * 0.62)
    for mao, sinal in (("hand", -1.0), ("hand2", 1.0)):
        rot = pose.get(mao)
        if rot is not None:
            pose[mao] = Rotation3(
                math.radians(-90.0) + rot.x * 0.20,
                math.radians(30.0 * sinal) + rot.y * 0.20,
                math.radians(60.0 * sinal) + rot.z * 0.20,
            )


def amostrar_clipe_emote(
    clipe: ClipeEmote, tempo_segundos: float
) -> dict[str, Rotation3]:
    """Amostra a pose do rig interpolada no tempo ``tempo_segundos`` (intro + loop)."""
    q_seq, _p_seq, _r_seq, i0, i1, frac = _indice_e_fracao(tempo_segundos, clipe)
    pose = _interpolar_pose(q_seq[i0], q_seq[i1], frac)
    if clipe.estilo == "celebration_dance":
        _ajustar_celebration_dance(pose)
    if clipe.peso_mistura < 1.0 - 1e-6:
        peso = clipe.peso_mistura
        return {
            g: Rotation3(r.x * peso, r.y * peso, r.z * peso)
            for g, r in pose.items()
        }
    return pose


def amostrar_pernas_emote(
    clipe: ClipeEmote, tempo_segundos: float
) -> dict[str, float]:
    """Amostra canais de pernas interpolados no tempo ``tempo_segundos`` (intro + loop)."""
    _q_seq, p_seq, _r_seq, i0, i1, frac = _indice_e_fracao(tempo_segundos, clipe)
    return _interpolar_pernas(p_seq[i0], p_seq[i1], frac)


def _slerp_quat(
    q0: tuple[float, float, float, float],
    q1: tuple[float, float, float, float],
    t: float,
) -> tuple[float, float, float, float]:
    import math

    w0, x0, y0, z0 = q0
    w1, x1, y1, z1 = q1
    dot = w0 * w1 + x0 * x1 + y0 * y1 + z0 * z1
    if dot < 0.0:
        w1, x1, y1, z1 = -w1, -x1, -y1, -z1
        dot = -dot
    if dot > 0.9995:
        w = w0 + (w1 - w0) * t
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        z = z0 + (z1 - z0) * t
        n = math.sqrt(w * w + x * x + y * y + z * z)
        return (w / n, x / n, y / n, z / n) if n > 1e-9 else (1.0, 0.0, 0.0, 0.0)
    dot = max(-1.0, min(1.0, dot))
    theta_0 = math.acos(dot)
    sin_theta_0 = math.sin(theta_0)
    theta = theta_0 * t
    sin_theta = math.sin(theta)
    s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
    s1 = sin_theta / sin_theta_0
    return (
        s0 * w0 + s1 * w1,
        s0 * x0 + s1 * x1,
        s0 * y0 + s1 * y1,
        s0 * z0 + s1 * z1,
    )


def amostrar_raiz_emote(
    clipe: ClipeEmote, tempo_segundos: float
) -> tuple[float, float]:
    """Amostra ``(dz_pelvis, giro_corpo_graus)`` no tempo ``tempo_segundos``."""
    _q_seq, _p_seq, r_seq, i0, i1, frac = _indice_e_fracao(tempo_segundos, clipe)
    dz0, g0 = r_seq[i0]
    dz1, g1 = r_seq[i1]
    giro = g0 + (((g1 - g0 + 180.0) % 360.0) - 180.0) * frac
    return (
        dz0 + (dz1 - dz0) * frac,
        ((giro + 180.0) % 360.0) - 180.0,
    )


def amostrar_deslocamento_emote(clipe: ClipeEmote, tempo_segundos: float) -> tuple[float, float]:
    """Amostra o trajeto horizontal da pelve no mesmo instante que a pose."""
    if not clipe.deslocamento:
        return (0.0, 0.0)
    quadros, _, _, i, j, u = _indice_e_fracao(tempo_segundos, clipe)
    if quadros is clipe.quadros:
        pontos = clipe.deslocamento
    else:
        pontos = (*clipe.deslocamento_intro, clipe.deslocamento[0])
    ax, ay = pontos[i]
    bx, by = pontos[j]
    return (ax + (bx - ax) * u, ay + (by - ay) * u)


def amostrar_orientacao_raiz_emote(
    clipe: ClipeEmote, tempo_segundos: float
) -> tuple[float, float, float, float] | None:
    """Amostra quaternion 3D ``(w, x, y, z)`` da raiz quando o emote tem acrobacia 3D."""
    t_quadros = max(0.0, tempo_segundos) * clipe.fps
    n_intro = len(clipe.quadros_intro)
    if n_intro > 0 and t_quadros < n_intro:
        if not clipe.quat_intro:
            return None
        idx0 = min(n_intro - 1, int(t_quadros))
        frac = t_quadros - idx0
        if idx0 + 1 < len(clipe.quat_intro):
            return _slerp_quat(clipe.quat_intro[idx0], clipe.quat_intro[idx0 + 1], frac)
        if clipe.quat_raiz:
            return _slerp_quat(clipe.quat_intro[idx0], clipe.quat_raiz[0], frac)
        return clipe.quat_intro[idx0]
    if not clipe.quat_raiz:
        return None
    n_loop = len(clipe.quat_raiz)
    if not clipe.em_loop:
        pos = min(float(n_loop - 1), max(0.0, t_quadros - n_intro))
        idx0 = min(n_loop - 1, int(pos))
        idx1 = min(n_loop - 1, idx0 + 1)
        return _slerp_quat(clipe.quat_raiz[idx0], clipe.quat_raiz[idx1], pos - int(pos))
    pos_loop = (t_quadros - n_intro) % n_loop
    idx0 = int(pos_loop) % n_loop
    idx1 = (idx0 + 1) % n_loop
    return _slerp_quat(clipe.quat_raiz[idx0], clipe.quat_raiz[idx1], pos_loop - int(pos_loop))


def duracao_clipe_emote(clipe: ClipeEmote) -> float:
    """Duração total em segundos (intro + loop) do clipe carregado."""
    taxa = max(1e-6, clipe.fps * clipe.velocidade)
    return (len(clipe.quadros_intro) + len(clipe.quadros)) / taxa


def amostrar_dedos_emote(
    clipe: ClipeEmote,
    tempo_segundos: float,
) -> tuple[tuple[float, float, float, float, float], tuple[float, float, float, float, float]] | None:
    """Amostra flexões individuais dos 5 dedos ``(direita, esquerda)`` em ``[0, 1]``."""
    _q_seq, _p_seq, _r_seq, idx0, idx1, frac = _indice_e_fracao(tempo_segundos, clipe)
    n_intro = len(clipe.quadros_intro)
    na_intro = n_intro > 0 and max(0.0, tempo_segundos) * clipe.fps < n_intro
    if na_intro:
        if idx0 >= len(clipe.dedos_intro):
            return None
        r0, l0 = clipe.dedos_intro[idx0]
        if idx1 < len(clipe.dedos_intro):
            r1, l1 = clipe.dedos_intro[idx1]
        elif clipe.dedos:
            r1, l1 = clipe.dedos[0]
        else:
            r1, l1 = r0, l0
    else:
        if not clipe.dedos:
            return None
        r0, l0 = clipe.dedos[min(idx0, len(clipe.dedos) - 1)]
        r1, l1 = clipe.dedos[min(idx1, len(clipe.dedos) - 1)]
    r_vals = tuple(
        max(0.0, min(1.0, r0[i] + (r1[i] - r0[i]) * frac))
        for i in range(5)
    )
    l_vals = tuple(
        max(0.0, min(1.0, l0[i] + (l1[i] - l0[i]) * frac))
        for i in range(5)
    )
    return (r_vals, l_vals)  # type: ignore[return-value]


_PARES_ESPELHO: tuple[tuple[str, str], ...] = (
    ("shoulder", "shoulder2"),
    ("right-arm", "left-arm"),
    ("ant-arm", "ant-arm2"),
    ("hand", "hand2"),
    ("fingers", "fingers2"),
    ("antena-direita", "antena-esquerda"),
    ("olho-direito", "olho-esquerdo"),
    ("sobrancelha-direita", "sobrancelha-esquerda"),
)
_MAPA_ESPELHO_GRUPOS: dict[str, str] = {
    a: b for p in _PARES_ESPELHO for a, b in (p, (p[1], p[0]))
}


def espelhar_pose_rig(pose: dict[str, Rotation3]) -> dict[str, Rotation3]:
    """Espelha uma pose local esquerda<->direita preservando eixo sagital X."""
    saida: dict[str, Rotation3] = {}
    for grupo, rot in pose.items():
        destino = _MAPA_ESPELHO_GRUPOS.get(grupo, grupo)
        saida[destino] = Rotation3(x=rot.x, y=-rot.y, z=-rot.z)
    return saida


def espelhar_canais_pernas(canais: dict[str, float]) -> dict[str, float]:
    """Espelha canais de pernas esquerda<->direita."""
    saida: dict[str, float] = {}
    for suf in ("", "_knee", "_lift", "_ankle"):
        r_val = canais.get(f"right{suf}")
        l_val = canais.get(f"left{suf}")
        if l_val is not None:
            saida[f"right{suf}"] = l_val
        if r_val is not None:
            saida[f"left{suf}"] = r_val
    for suf in ("_roll", "_yaw"):
        r_val = canais.get(f"right{suf}")
        l_val = canais.get(f"left{suf}")
        if l_val is not None:
            saida[f"right{suf}"] = -l_val
        if r_val is not None:
            saida[f"left{suf}"] = -r_val
    return saida


def amostrar_clipe_completo(
    clipe: ClipeEmote,
    tempo_segundos: float,
    *,
    espelhar: bool = False,
) -> tuple[
    dict[str, Rotation3],
    dict[str, float],
    float,
    float,
    tuple[float, float, float, float] | None,
    tuple[tuple[float, float, float, float, float], tuple[float, float, float, float, float]] | None,
]:
    """Amostra pose do rig, canais de pernas, raiz, orientação 3D e dedos de uma vez."""
    pose = amostrar_clipe_emote(clipe, tempo_segundos)
    pernas = amostrar_pernas_emote(clipe, tempo_segundos)
    dz, yaw = amostrar_raiz_emote(clipe, tempo_segundos)
    quat = amostrar_orientacao_raiz_emote(clipe, tempo_segundos)
    dedos = amostrar_dedos_emote(clipe, tempo_segundos)
    if espelhar:
        pose = espelhar_pose_rig(pose)
        pernas = espelhar_canais_pernas(pernas)
        yaw = -yaw
        if quat is not None:
            qw, qx, qy, qz = quat
            quat = (qw, qx, -qy, -qz)
        if dedos is not None:
            dedos = (dedos[1], dedos[0])
    return pose, pernas, dz, yaw, quat, dedos


def _listar_clipes_em(pasta_sub: str) -> tuple[str, ...]:
    pasta = assets_dir() / "animation" / pasta_sub
    if not pasta.exists():
        return ()
    return tuple(
        sorted(
            p.stem
            for p in pasta.glob("*.json")
            if p.stem != "resumo_extracao"
        )
    )


def listar_clipes_emote() -> tuple[str, ...]:
    """Lista os nomes de estilos de emote disponíveis em ``assets/animation/loops``."""
    return _listar_clipes_em("loops")


def listar_clipes_acao() -> tuple[str, ...]:
    """Lista os nomes de clipes de ação/locomoção em ``assets/animation/acoes``."""
    return _listar_clipes_em("acoes")


listar_clipes_danca = listar_clipes_emote
carregar_clipe_danca = carregar_clipe_emote


def amostrar_clipe_danca(
    clipe_ou_nome: str | ClipeEmote, tempo_segundos: float
) -> dict[str, tuple[float, float, float]] | None:
    """Amostra o clipe por nome ou instância devolvendo tuplas ``(x, y, z)``."""
    clipe = (
        carregar_clipe_emote(clipe_ou_nome)
        if isinstance(clipe_ou_nome, str)
        else clipe_ou_nome
    )
    if clipe is None:
        return None
    pose = amostrar_clipe_emote(clipe, tempo_segundos)
    return {k: (r.x, r.y, r.z) for k, r in pose.items()}

