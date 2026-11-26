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
        velocidade = max(0.35, min(3.2, float(dados.get("velocidade", 1.0))))
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


_CACHE_OVERRIDE: dict[tuple[int, str, tuple[tuple[str, object], ...]], ClipeEmote] = {}


def _aplicar_override_clipe(clipe: ClipeEmote, nome: str) -> ClipeEmote:
    override = danca_ativa().get("clipes", {}).get(nome)
    if not isinstance(override, dict) or not override:
        return clipe
    chave = (id(clipe), nome, tuple(sorted(override.items())))
    cached = _CACHE_OVERRIDE.get(chave)
    if cached is not None:
        return cached
    if len(_CACHE_OVERRIDE) > 256:
        _CACHE_OVERRIDE.clear()
    res = replace(
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
    _CACHE_OVERRIDE[chave] = res
    return res


def _suavizar_raiz_clipe(
    raiz: tuple[tuple[float, float], ...],
    *,
    em_loop: bool,
) -> tuple[tuple[float, float], ...]:
    """Filtra picos bruscos de giro (> 30°/quadro) e degraus de emenda em ``raiz``."""
    n = len(raiz)
    if n < 5:
        return raiz
    buf = list(raiz)
    indices: set[int] = set()
    fim = n if em_loop else n - 1
    for i in range(fim):
        g0 = buf[i][1]
        g1 = buf[(i + 1) % n][1]
        diff = abs(((g1 - g0 + 180.0) % 360.0) - 180.0)
        if diff > 30.0:
            for off in (-1, 0, 1, 2):
                idx = i + off
                if em_loop:
                    indices.add(idx % n)
                elif 1 <= idx <= n - 2:
                    indices.add(idx)
    if em_loop:
        seam = abs(((buf[0][1] - buf[-1][1] + 180.0) % 360.0) - 180.0)
        if seam > 6.0:
            indices.update({(n - 2) % n, n - 1, 0, 1})
    if not indices:
        return raiz
    for _ in range(4):
        prox = list(buf)
        for idx in indices:
            dz_a, ga = buf[(idx - 1) % n]
            dz_c, gc = buf[idx]
            dz_b, gb = buf[(idx + 1) % n]
            da = ((ga - gc + 180.0) % 360.0) - 180.0
            db = ((gb - gc + 180.0) % 360.0) - 180.0
            g_novo = ((gc + (da + db) * 0.25 + 180.0) % 360.0) - 180.0
            dz_novo = dz_c + ((dz_a - dz_c) + (dz_b - dz_c)) * 0.25
            prox[idx] = (dz_novo, g_novo)
        buf = prox
    return tuple(buf)


def _suavizar_quat_clipe(
    quats: tuple[tuple[float, float, float, float], ...],
    *,
    em_loop: bool,
) -> tuple[tuple[float, float, float, float], ...]:
    """Filtra saltos angulares > 30°/quadro em ``quat_raiz`` preservando inversões 3D."""
    n = len(quats)
    if n < 5:
        return quats
    buf = list(quats)
    indices: set[int] = set()
    fim = n if em_loop else n - 1
    cos_lim = math.cos(math.radians(15.0))  # dot < cos(15°) => ângulo 3D > 30°
    for i in range(fim):
        q0, q1 = buf[i], buf[(i + 1) % n]
        dot = abs(q0[0] * q1[0] + q0[1] * q1[1] + q0[2] * q1[2] + q0[3] * q1[3])
        if dot < cos_lim:
            for off in (-1, 0, 1, 2):
                idx = i + off
                if em_loop:
                    indices.add(idx % n)
                elif 1 <= idx <= n - 2:
                    indices.add(idx)
    if not indices:
        return quats
    for _ in range(4):
        prox = list(buf)
        for idx in indices:
            medio = _slerp_quat(buf[(idx - 1) % n], buf[(idx + 1) % n], 0.5)
            prox[idx] = _slerp_quat(buf[idx], medio, 0.5)
        buf = prox
    return tuple(buf)


def _costurar_intro_no_loop(
    q_intro: tuple[dict[str, Rotation3], ...],
    p_intro: tuple[dict[str, float], ...],
    q_loop0: dict[str, Rotation3],
    p_loop0: dict[str, float],
) -> tuple[tuple[dict[str, Rotation3], ...], tuple[dict[str, float], ...]]:
    """Suaviza os últimos 3 quadros da intro quando há degrau relevante na emenda intro→loop."""
    n_in = len(q_intro)
    if n_in < 4:
        return q_intro, p_intro
    q_buf = [dict(q) for q in q_intro]
    p_buf = [dict(p) for p in p_intro]
    alterou_q = False
    if _distancia_ang_poses(q_buf[-1], q_loop0) > 0.14:
        alterou_q = True
        zero = Rotation3()
        for k, peso in ((n_in - 3, 0.15), (n_in - 2, 0.38), (n_in - 1, 0.70)):
            for grupo, r_alvo in q_loop0.items():
                r_cur = q_buf[k].get(grupo, zero)
                dx = ((r_alvo.x - r_cur.x + math.pi) % math.tau) - math.pi
                dy = ((r_alvo.y - r_cur.y + math.pi) % math.tau) - math.pi
                dz = ((r_alvo.z - r_cur.z + math.pi) % math.tau) - math.pi
                q_buf[k][grupo] = Rotation3(
                    r_cur.x + dx * peso,
                    r_cur.y + dy * peso,
                    r_cur.z + dz * peso,
                )
    alterou_p = False
    if len(p_buf) == n_in and p_loop0:
        max_dp = max((abs(p_loop0[c] - p_buf[-1].get(c, 0.0)) for c in p_loop0), default=0.0)
        if max_dp > 10.0:
            alterou_p = True
            for k, peso in ((n_in - 3, 0.15), (n_in - 2, 0.38), (n_in - 1, 0.70)):
                for canal, v_alvo in p_loop0.items():
                    v_cur = p_buf[k].get(canal, 0.0)
                    p_buf[k][canal] = v_cur + (v_alvo - v_cur) * peso
    return (tuple(q_buf) if alterou_q else q_intro), (tuple(p_buf) if alterou_p else p_intro)


def _carregar_clipe_em_base(pasta_sub: str, estilo: str) -> ClipeEmote | None:
    clipe = _carregar_clipe_em(pasta_sub, estilo)
    if clipe is None:
        return None
    clipe = _deduplicar_fim_loop(clipe)
    quadros, pernas = _suavizar_clipe(
        clipe.quadros,
        clipe.quadros_pernas,
        em_loop=clipe.em_loop,
    )
    q_intro, p_intro = _suavizar_clipe(
        clipe.quadros_intro,
        clipe.quadros_pernas_intro,
        em_loop=False,
    )
    if q_intro and quadros:
        q_intro, p_intro = _costurar_intro_no_loop(q_intro, p_intro, quadros[0], pernas[0])
    raiz = _suavizar_raiz_clipe(clipe.raiz, em_loop=clipe.em_loop)
    quat_raiz = _suavizar_quat_clipe(clipe.quat_raiz, em_loop=clipe.em_loop)
    return replace(
        clipe,
        quadros_intro=q_intro,
        quadros_pernas_intro=p_intro,
        quadros=quadros,
        quadros_pernas=pernas,
        raiz=raiz,
        quat_raiz=quat_raiz,
    )


@lru_cache(maxsize=64)
def _carregar_clipe_loop_suave(estilo: str) -> ClipeEmote | None:
    return _carregar_clipe_em_base("loops", estilo)


def carregar_clipe_emote(estilo: str) -> ClipeEmote | None:
    """Carrega o clipe de loop de ``assets/animation/loops/<estilo>.json`` se existir."""
    clipe = _carregar_clipe_loop_suave(estilo)
    if clipe is None:
        return None
    return _aplicar_override_clipe(clipe, estilo)


def _distancia_ang_poses(a: dict[str, Rotation3], b: dict[str, Rotation3]) -> float:
    pior = 0.0
    for grupo, ra in a.items():
        rb = b.get(grupo)
        if rb is None:
            continue
        pior = max(
            pior,
            abs(((rb.x - ra.x + math.pi) % math.tau) - math.pi),
            abs(((rb.y - ra.y + math.pi) % math.tau) - math.pi),
            abs(((rb.z - ra.z + math.pi) % math.tau) - math.pi),
        )
    return pior


def _deduplicar_fim_loop(clipe: ClipeEmote) -> ClipeEmote:
    """Remove o quadro final duplicado de clips cíclicos quando coincide com o quadro 0."""
    n = len(clipe.quadros)
    if not clipe.em_loop or n < 4:
        return clipe
    if _distancia_ang_poses(clipe.quadros[0], clipe.quadros[-1]) >= 0.04:
        return clipe
    p0 = clipe.quadros_pernas[0] if clipe.quadros_pernas else {}
    p1 = clipe.quadros_pernas[-1] if clipe.quadros_pernas else {}
    diff_pernas = max(
        (abs(p1.get(k, 0.0) - p0.get(k, 0.0)) for k in (set(p0) | set(p1))),
        default=0.0,
    )
    if diff_pernas >= 1.5:
        return clipe
    if len(clipe.raiz) == n:
        dz0, g0 = clipe.raiz[0]
        dz1, g1 = clipe.raiz[-1]
        if abs(dz1 - dz0) >= 0.01 or abs(((g1 - g0 + 180.0) % 360.0) - 180.0) >= 1.0:
            return clipe
    return replace(
        clipe,
        quadros=clipe.quadros[:-1],
        quadros_pernas=clipe.quadros_pernas[:-1] if len(clipe.quadros_pernas) == n else clipe.quadros_pernas,
        raiz=clipe.raiz[:-1] if len(clipe.raiz) == n else clipe.raiz,
        quat_raiz=clipe.quat_raiz[:-1] if len(clipe.quat_raiz) == n else clipe.quat_raiz,
        deslocamento=clipe.deslocamento[:-1] if len(clipe.deslocamento) == n else clipe.deslocamento,
        dedos=clipe.dedos[:-1] if len(clipe.dedos) == n else clipe.dedos,
    )


def _suavizar_pernas_clipe(
    pernas: tuple[dict[str, float], ...],
    *,
    em_loop: bool,
) -> tuple[dict[str, float], ...]:
    n = len(pernas)
    if n < 5:
        return pernas
    buf = [dict(p) for p in pernas]
    chaves = set().union(*(p.keys() for p in buf))
    alterou = False
    for canal in chaves:
        indices: set[int] = set()
        inicio_i = 0 if em_loop else 1
        fim_i = n if em_loop else n - 1
        for i in range(inicio_i, fim_i):
            ant = buf[(i - 1) % n].get(canal, 0.0)
            cur = buf[i].get(canal, 0.0)
            seg = buf[(i + 1) % n].get(canal, 0.0)
            d_in = cur - ant
            d_out = seg - cur
            # Remove picos isolados com reversão brusca (> 22°) ou saltos monotônicos > 30°/quadro.
            if abs(d_in) > 22.0 and abs(d_out) > 22.0 and d_in * d_out < 0.0:
                indices.add(i)
            elif abs(d_in) > 30.0 or abs(d_out) > 30.0:
                indices.add(i)
        if not indices:
            continue
        alterou = True
        medias = {i: (buf[(i - 1) % n].get(canal, 0.0) + buf[(i + 1) % n].get(canal, 0.0)) * 0.5 for i in indices}
        for i, v in medias.items():
            if canal in buf[i]:
                buf[i][canal] = v
    return tuple(buf) if alterou else pernas


def _coletar_indices_picos_grupo(
    buf: list[dict[str, Rotation3]],
    grupo: str,
    limiar: float,
    em_loop: bool,
) -> set[int]:
    n = len(buf)
    zero = Rotation3()
    indices: set[int] = set()
    fim = n if em_loop else n - 1
    for i in range(fim):
        ra = buf[i].get(grupo, zero)
        rb = buf[(i + 1) % n].get(grupo, zero)
        d = max(
            abs(((rb.x - ra.x + math.pi) % math.tau) - math.pi),
            abs(((rb.y - ra.y + math.pi) % math.tau) - math.pi),
            abs(((rb.z - ra.z + math.pi) % math.tau) - math.pi),
        )
        if d <= limiar:
            continue
        for off in (-2, -1, 0, 1, 2):
            idx = i + off
            if em_loop:
                indices.add(idx % n)
            elif 1 <= idx <= n - 2:
                indices.add(idx)
    return indices


def _suavizar_indices_grupo(
    buf: list[dict[str, Rotation3]],
    grupo: str,
    indices: set[int],
    passagens: int,
) -> None:
    if not indices:
        return
    n = len(buf)
    zero = Rotation3()
    for _ in range(passagens):
        proximo = [q.get(grupo, zero) for q in buf]
        for idx in indices:
            ant = buf[(idx - 1) % n].get(grupo, zero)
            cur = buf[idx].get(grupo, zero)
            seg = buf[(idx + 1) % n].get(grupo, zero)
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


def _suavizar_emenda_loop_clipe(
    buf: list[dict[str, Rotation3]], todos: set[str]
) -> None:
    n = len(buf)
    zero = Rotation3()
    emenda_idx = {idx % n for idx in (-3, -2, -1, 0, 1, 2)}
    for grupo in todos:
        max_borda = 0.0
        for ia, ib in ((-2, -1), (-1, 0), (0, 1)):
            ra = buf[ia % n].get(grupo, zero)
            rb = buf[ib % n].get(grupo, zero)
            d_borda = max(
                abs(((rb.x - ra.x + math.pi) % math.tau) - math.pi),
                abs(((rb.y - ra.y + math.pi) % math.tau) - math.pi),
                abs(((rb.z - ra.z + math.pi) % math.tau) - math.pi),
            )
            max_borda = max(max_borda, d_borda)
        if max_borda > 0.28:
            _suavizar_indices_grupo(buf, grupo, emenda_idx, 5)


def _suavizar_clipe(
    quadros: tuple[dict[str, Rotation3], ...],
    quadros_pernas: tuple[dict[str, float], ...],
    *,
    em_loop: bool,
) -> tuple[tuple[dict[str, Rotation3], ...], tuple[dict[str, float], ...]]:
    """Suaviza flips de gimbal, picos súbitos de membros/pernas e degraus de emenda."""
    pernas_suaves = _suavizar_pernas_clipe(quadros_pernas, em_loop=em_loop)
    if len(quadros) < 5:
        return quadros, pernas_suaves
    buf = [dict(q) for q in quadros]
    todos = set().union(*(q.keys() for q in buf))
    for grupo in ("hand", "hand2"):
        picos = _coletar_indices_picos_grupo(buf, grupo, 0.24, em_loop)
        _suavizar_indices_grupo(buf, grupo, picos, 12)
    for grupo in todos - {"hand", "hand2"}:
        picos = _coletar_indices_picos_grupo(buf, grupo, 0.38, em_loop)
        _suavizar_indices_grupo(buf, grupo, picos, 6)
    if em_loop:
        _suavizar_emenda_loop_clipe(buf, todos)
    return tuple(buf), pernas_suaves


@lru_cache(maxsize=64)
def _carregar_clipe_acao_suave(nome: str) -> ClipeEmote | None:
    return _carregar_clipe_em_base("acoes", nome)


def carregar_clipe_acao(nome: str) -> ClipeEmote | None:
    """Carrega um clipe de ação/locomoção em ``assets/animation/acoes/<nome>.json``."""
    clipe = _carregar_clipe_acao_suave(nome)
    if clipe is None:
        return None
    return _aplicar_override_clipe(clipe, nome)


def _unwrap_em_torno(ref: float, alvo: float, periodo: float) -> float:
    meio = periodo * 0.5
    return ref + (((alvo - ref + meio) % periodo) - meio)


def _catmull_rom_escalar(p0: float, p1: float, p2: float, p3: float, u: float) -> float:
    u2 = u * u
    u3 = u2 * u
    return 0.5 * (
        (2.0 * p1)
        + (-p0 + p2) * u
        + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * u2
        + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * u3
    )


def _catmull_rom_ang(
    p0: float, p1: float, p2: float, p3: float, u: float, periodo: float = math.tau
) -> float:
    a0 = _unwrap_em_torno(p1, p0, periodo)
    a2 = _unwrap_em_torno(p1, p2, periodo)
    a3 = _unwrap_em_torno(a2, p3, periodo)
    return _catmull_rom_escalar(a0, p1, a2, a3, u)


def _quatro_indices(n: int, idx0: int, idx1: int, em_loop: bool) -> tuple[int, int, int, int]:
    if n <= 1:
        return (0, 0, 0, 0)
    if em_loop:
        return ((idx0 - 1) % n, idx0, idx1, (idx1 + 1) % n)
    return (max(0, idx0 - 1), idx0, idx1, min(n - 1, idx1 + 1))


def _interpolar_pose_catmull(
    seq: tuple[dict[str, Rotation3], ...],
    i_ant: int,
    i0: int,
    i1: int,
    i_prox: int,
    u: float,
) -> dict[str, Rotation3]:
    p_ant, pa, pb, p_prox = seq[i_ant], seq[i0], seq[i1], seq[i_prox]
    chaves = set(pa.keys()) | set(pb.keys())
    zero = Rotation3()
    saida: dict[str, Rotation3] = {}
    for k in chaves:
        r0 = p_ant.get(k, pa.get(k, zero))
        r1 = pa.get(k, zero)
        r2 = pb.get(k, zero)
        r3 = p_prox.get(k, pb.get(k, zero))
        saida[k] = Rotation3(
            _catmull_rom_ang(r0.x, r1.x, r2.x, r3.x, u),
            _catmull_rom_ang(r0.y, r1.y, r2.y, r3.y, u),
            _catmull_rom_ang(r0.z, r1.z, r2.z, r3.z, u),
        )
    return saida


def _interpolar_pernas_catmull(
    seq: tuple[dict[str, float], ...],
    i_ant: int,
    i0: int,
    i1: int,
    i_prox: int,
    u: float,
) -> dict[str, float]:
    p_ant, pa, pb, p_prox = seq[i_ant], seq[i0], seq[i1], seq[i_prox]
    chaves = set(pa.keys()) | set(pb.keys())
    return {
        k: _catmull_rom_escalar(
            p_ant.get(k, pa.get(k, 0.0)),
            pa.get(k, 0.0),
            pb.get(k, 0.0),
            p_prox.get(k, pb.get(k, 0.0)),
            u,
        )
        for k in chaves
    }


def _tempo_com_recorte(tempo_segundos: float, clipe: ClipeEmote) -> float:
    inicio = max(0.0, clipe.inicio_s)
    t_bruto = max(0.0, tempo_segundos)
    dur_intro = len(clipe.quadros_intro) / max(1.0, clipe.fps)
    if clipe.fim_s is not None and clipe.fim_s > inicio:
        if dur_intro > 0.0 and t_bruto < dur_intro:
            return min(clipe.fim_s, inicio + t_bruto)
        loop_inicio = max(inicio, dur_intro)
        trecho = max(1e-6, clipe.fim_s - loop_inicio)
        t_pos = max(0.0, t_bruto - dur_intro)
        return loop_inicio + ((t_pos % trecho) if clipe.em_loop else min(trecho, t_pos))
    return t_bruto + inicio


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
        # Transição contínua do último quadro da intro para o loop (inclui quadros[1] como tangente p3)
        q_ext = (*clipe.quadros_intro, clipe.quadros[0], clipe.quadros[1 % len(clipe.quadros)])
        p_ext = (*clipe.quadros_pernas_intro, clipe.quadros_pernas[0], clipe.quadros_pernas[1 % len(clipe.quadros_pernas)])
        r_ext = (*clipe.raiz_intro, clipe.raiz[0], clipe.raiz[1 % len(clipe.raiz)])
        return (q_ext, p_ext, r_ext, idx0, idx0 + 1, frac)

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


def _indices_catmull(
    q_seq: tuple[dict[str, Rotation3], ...],
    clipe: ClipeEmote,
    i0: int,
    i1: int,
) -> tuple[int, int, int, int]:
    em_loop = q_seq is clipe.quadros and clipe.em_loop
    return _quatro_indices(len(q_seq), i0, i1, em_loop)


def amostrar_clipe_emote(
    clipe: ClipeEmote, tempo_segundos: float
) -> dict[str, Rotation3]:
    """Amostra a pose do rig interpolada no tempo ``tempo_segundos`` (intro + loop)."""
    q_seq, _p_seq, _r_seq, i0, i1, frac = _indice_e_fracao(tempo_segundos, clipe)
    ia, ib, ic, id_ = _indices_catmull(q_seq, clipe, i0, i1)
    pose = _interpolar_pose_catmull(q_seq, ia, ib, ic, id_, frac)
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
    q_seq, p_seq, _r_seq, i0, i1, frac = _indice_e_fracao(tempo_segundos, clipe)
    ia, ib, ic, id_ = _indices_catmull(q_seq, clipe, i0, i1)
    return _interpolar_pernas_catmull(p_seq, ia, ib, ic, id_, frac)


def _slerp_quat(
    q0: tuple[float, float, float, float],
    q1: tuple[float, float, float, float],
    t: float,
) -> tuple[float, float, float, float]:
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
    q_seq, _p_seq, r_seq, i0, i1, frac = _indice_e_fracao(tempo_segundos, clipe)
    ia, ib, ic, id_ = _quatro_indices(
        len(r_seq), i0, i1, q_seq is clipe.quadros and clipe.em_loop
    )
    dz = _catmull_rom_escalar(r_seq[ia][0], r_seq[ib][0], r_seq[ic][0], r_seq[id_][0], frac)
    giro = _catmull_rom_ang(
        r_seq[ia][1], r_seq[ib][1], r_seq[ic][1], r_seq[id_][1], frac, periodo=360.0
    )
    return (dz, ((giro + 180.0) % 360.0) - 180.0)


def amostrar_deslocamento_emote(clipe: ClipeEmote, tempo_segundos: float) -> tuple[float, float]:
    """Amostra o trajeto horizontal da pelve no mesmo instante que a pose."""
    if not clipe.deslocamento:
        return (0.0, 0.0)
    quadros, _, _, i, j, u = _indice_e_fracao(tempo_segundos, clipe)
    em_loop = quadros is clipe.quadros and clipe.em_loop
    pontos = (
        clipe.deslocamento
        if quadros is clipe.quadros
        else (*clipe.deslocamento_intro, clipe.deslocamento[0])
    )
    ia, ib, ic, id_ = _quatro_indices(len(pontos), i, j, em_loop)
    x = _catmull_rom_escalar(pontos[ia][0], pontos[ib][0], pontos[ic][0], pontos[id_][0], u)
    y = _catmull_rom_escalar(pontos[ia][1], pontos[ib][1], pontos[ic][1], pontos[id_][1], u)
    return (x, y)


def amostrar_orientacao_raiz_emote(
    clipe: ClipeEmote, tempo_segundos: float
) -> tuple[float, float, float, float] | None:
    """Amostra quaternion 3D ``(w, x, y, z)`` da raiz quando o emote tem acrobacia 3D."""
    t_quadros = max(0.0, _tempo_com_recorte(tempo_segundos, clipe)) * clipe.fps
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
    q_seq, _p_seq, _r_seq, idx0, idx1, frac = _indice_e_fracao(tempo_segundos, clipe)
    n_intro = len(clipe.quadros_intro)
    na_intro = (
        n_intro > 0
        and max(0.0, _tempo_com_recorte(tempo_segundos, clipe)) * clipe.fps < n_intro
    )
    if na_intro:
        if idx0 >= len(clipe.dedos_intro):
            return None
        seq = (
            (*clipe.dedos_intro, clipe.dedos[0])
            if clipe.dedos
            else clipe.dedos_intro
        )
        em_loop = False
    else:
        if not clipe.dedos:
            return None
        seq = clipe.dedos
        em_loop = q_seq is clipe.quadros and clipe.em_loop
    ia, ib, ic, id_ = _quatro_indices(
        len(seq), min(idx0, len(seq) - 1), min(idx1, len(seq) - 1), em_loop
    )
    r_vals = tuple(
        max(
            0.0,
            min(
                1.0,
                _catmull_rom_escalar(
                    seq[ia][0][i], seq[ib][0][i], seq[ic][0][i], seq[id_][0][i], frac
                ),
            ),
        )
        for i in range(5)
    )
    l_vals = tuple(
        max(
            0.0,
            min(
                1.0,
                _catmull_rom_escalar(
                    seq[ia][1][i], seq[ib][1][i], seq[ic][1][i], seq[id_][1][i], frac
                ),
            ),
        )
        for i in range(5)
    )
    return (r_vals, l_vals)  # type: ignore[return-value]


_PARES_ESPELHO: tuple[tuple[str, str], ...] = (
    ("shoulder", "shoulder2"),
    ("right-arm", "left-arm"),
    ("ant-arm", "ant-arm2"),
    ("hand", "hand2"),
    ("fingers", "fingers2"),
    ("fone-direito", "fone-esquerdo"),
    ("antena-direita", "antena-esquerda"),
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

