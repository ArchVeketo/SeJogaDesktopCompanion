"""Leitura segura por AST, validação e gravação atômica de ``animation.py``.

Sem dependências de Panda3D, Qt ou Win32.
"""

from __future__ import annotations

import ast
import hashlib
import math
import os
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sejoga.editor.esquema import (
    CURVAS_VALIDAS,
    TOP_LEVEL_KEYS,
    ancora_vfx_valida,
    grupo_rig_valido,
)

CAMINHO_ANIMATION_PADRAO = (
    Path(__file__).resolve().parents[1] / "animacao" / "animation.py"
)


class PersistenciaAnimacaoError(ValueError):
    """Erro de leitura, sintaxe ou validação do módulo ``animation.py``."""


class ConflitoArquivoExternoError(PersistenciaAnimacaoError):
    """Sinaliza modificação externa em disco desde a última abertura/salvamento."""

    def __init__(self, sha_esperado: str, sha_atual: str) -> None:
        """Armazena os hashes esperado e encontrado no conflito."""
        super().__init__(
            "O arquivo animation.py foi alterado externamente no disco "
            f"(esperado {sha_esperado[:8]}, atual {sha_atual[:8]})."
        )
        self.sha_esperado = sha_esperado
        self.sha_atual = sha_atual


# Aliases semânticos compatíveis.
ErroPersistenciaAnimacao = PersistenciaAnimacaoError
ConflitoArquivoExterno = ConflitoArquivoExternoError


@dataclass(frozen=True, slots=True)
class ArquivoAnimacao:
    """Snapshot carregado ou salvo de ``animation.py`` com assinatura em disco."""

    caminho: Path
    dados: dict[str, Any]
    sha256: str
    mtime_ns: int


def sha256_texto(texto: str) -> str:
    """Calcula o resumo SHA-256 UTF-8 para detecção de alterações externas."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _validar_numero(valor: Any, nome: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErroPersistenciaAnimacao(f"Campo '{nome}' deve ser numérico.")
    num = float(valor)
    if not math.isfinite(num):
        raise ErroPersistenciaAnimacao(f"Campo '{nome}' deve ser finito.")
    return num


def _validar_trio(valor: Any, nome: str) -> None:
    if not isinstance(valor, (tuple, list)) or len(valor) != 3:
        raise ErroPersistenciaAnimacao(f"Campo '{nome}' deve conter 3 eixos.")
    for idx, item in enumerate(valor):
        _validar_numero(item, f"{nome}[{idx}]")


def _validar_pista(
    pista: Any,
    nome: str,
    duracao: float,
    *,
    curvas: Any = None,
) -> None:
    if not isinstance(pista, (tuple, list)) or not pista:
        raise ErroPersistenciaAnimacao(f"Pista '{nome}' não pode ser vazia.")
    t_anterior = -math.inf
    for idx, item in enumerate(pista):
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ErroPersistenciaAnimacao(f"Chave {idx} de '{nome}' inválida.")
        t = _validar_numero(item[0], f"{nome}[{idx}].t")
        if t < 0.0 or t > duracao + 1e-6:
            raise ErroPersistenciaAnimacao(
                f"Tempo {t} em '{nome}' fora de [0, {duracao}]."
            )
        if t <= t_anterior and idx > 0:
            raise ErroPersistenciaAnimacao(
                f"Tempos não crescentes em '{nome}': {t_anterior} -> {t}."
            )
        t_anterior = t
        _validar_trio(item[1], f"{nome}[{idx}].valor")
    if curvas is not None:
        for idx, curva in enumerate(curvas):
            if curva not in CURVAS_VALIDAS:
                raise ErroPersistenciaAnimacao(
                    f"Curva inválida '{curva}' em '{nome}[{idx}]'."
                )


def _validar_bloco_trilhas(
    bloco: dict[str, Any],
    nome_acao: str,
    *,
    validar_grupos: bool = True,
) -> None:
    dur = _validar_numero(bloco.get("duration"), f"{nome_acao}.duration")
    if dur <= 0.0:
        raise ErroPersistenciaAnimacao(f"Duração inválida em '{nome_acao}': {dur}.")
    trilhas = bloco.get("tracks", {})
    if not isinstance(trilhas, dict):
        raise ErroPersistenciaAnimacao(f"Trilhas de '{nome_acao}' devem ser dict.")
    curvas_map = bloco.get("curvas", {})
    for grupo, pista in trilhas.items():
        if validar_grupos and not grupo_rig_valido(str(grupo)):
            raise ErroPersistenciaAnimacao(
                f"Grupo de rig inválido '{grupo}' em '{nome_acao}'."
            )
        _validar_pista(
            pista,
            f"{nome_acao}.{grupo}",
            dur,
            curvas=curvas_map.get(grupo) if isinstance(curvas_map, dict) else None,
        )


def _validar_janelas(janelas: Any, nome_acao: str, dur: float) -> None:
    if not isinstance(janelas, dict):
        raise ErroPersistenciaAnimacao(f"Janelas de '{nome_acao}' devem ser dict.")
    for nome_j, par in janelas.items():
        if not isinstance(par, (tuple, list)) or len(par) != 2:
            raise ErroPersistenciaAnimacao(f"Janela '{nome_acao}.{nome_j}' inválida.")
        ini = _validar_numero(par[0], f"{nome_acao}.{nome_j}[0]")
        fim = _validar_numero(par[1], f"{nome_acao}.{nome_j}[1]")
        if ini < 0.0 or fim > dur + 1e-6 or ini >= fim:
            raise ErroPersistenciaAnimacao(
                f"Intervalo inválido ({ini}, {fim}) em '{nome_acao}.{nome_j}'."
            )


def _validar_cenas_idle(cenas: Any) -> None:
    if not isinstance(cenas, dict):
        raise ErroPersistenciaAnimacao("'CENAS_IDLE' deve ser dict.")
    for nome, cena in cenas.items():
        if not isinstance(cena, dict):
            raise ErroPersistenciaAnimacao(f"Cena '{nome}' deve ser dict.")
        _validar_bloco_trilhas(cena, f"CENAS_IDLE.{nome}")
        dur = float(cena["duration"])
        _validar_numero(cena.get("blend_entrada_s", 0.0), f"{nome}.blend_entrada_s")
        _validar_numero(cena.get("blend_saida_s", 0.0), f"{nome}.blend_saida_s")
        _validar_janelas(cena.get("janelas_efeito", {}), nome, dur)
        desloc_j = cena.get("deslocamento_janela_s")
        if desloc_j is not None:
            _validar_janelas({"deslocamento": desloc_j}, nome, dur)
        if "deslocamento_corpo" in cena:
            _validar_trio(cena["deslocamento_corpo"], f"{nome}.deslocamento_corpo")


def _validar_respiracao(resp: Any) -> None:
    if not isinstance(resp, dict):
        raise ErroPersistenciaAnimacao("'RESPIRACAO' deve ser dict.")
    ciclo = resp.get("ciclo")
    if not isinstance(ciclo, (tuple, list)) or len(ciclo) < 2:
        raise ErroPersistenciaAnimacao("'RESPIRACAO.ciclo' deve ter ao menos 2 chaves.")
    dur_ciclo = _validar_numero(ciclo[-1][0], "RESPIRACAO.ciclo.fim")
    if dur_ciclo <= 0.0:
        raise ErroPersistenciaAnimacao("Duração do ciclo respiratório deve ser > 0.")
    _validar_pista(
        ciclo,
        "RESPIRACAO.ciclo",
        dur_ciclo,
        curvas=resp.get("ciclo_curvas"),
    )
    pers = resp.get("personalidades", {})
    if not isinstance(pers, dict):
        raise ErroPersistenciaAnimacao("'RESPIRACAO.personalidades' deve ser dict.")
    for nome, params in pers.items():
        freq = _validar_numero(params.get("frequencia"), f"RESPIRACAO.{nome}.freq")
        amp = _validar_numero(params.get("amplitude"), f"RESPIRACAO.{nome}.amp")
        bounce = _validar_numero(params.get("bounce"), f"RESPIRACAO.{nome}.bounce")
        if freq <= 0.0 or not (0.0 < amp <= 2.0) or not (0.0 <= bounce <= 1.0):
            raise ErroPersistenciaAnimacao(
                f"Parâmetros fora dos limites em RESPIRACAO.{nome}."
            )


def _validar_pose_danca(pose: Any, estilo: str, p_idx: int, s_idx: int) -> None:
    for grp, rot in pose.get("corpo", {}).items():
        if not grupo_rig_valido(str(grp)):
            raise PersistenciaAnimacaoError(
                f"Grupo inválido '{grp}' em DANCA.{estilo}[{p_idx}][{s_idx}]."
            )
        _validar_trio(rot, f"DANCA.{estilo}.{grp}")


def _validar_danca(danca: Any) -> None:
    if not isinstance(danca, dict):
        raise PersistenciaAnimacaoError("'DANCA' deve ser dict.")
    frases = danca.get("frases", {})
    if not isinstance(frases, dict):
        raise PersistenciaAnimacaoError("'DANCA.frases' deve ser dict.")
    for estilo, frase in frases.items():
        passos = frase.get("passos", ())
        if not passos:
            raise PersistenciaAnimacaoError(f"Frase de dança '{estilo}' sem passos.")
        for p_idx, passo in enumerate(passos):
            for s_idx, pose in enumerate(passo.get("poses", ())):
                _validar_pose_danca(pose, estilo, p_idx, s_idx)


def _validar_tentaculos(tent: Any) -> None:
    if not isinstance(tent, dict):
        raise ErroPersistenciaAnimacao("'TENTACULOS' deve ser dict.")
    for nome, saida in tent.get("saidas", {}).items():
        if _validar_numero(saida.get("duracao_s"), f"TENTACULOS.{nome}.duracao_s") <= 0:
            raise ErroPersistenciaAnimacao(f"Duração inválida em '{nome}'.")
    for nome, ond in tent.get("ondulacoes", {}).items():
        if _validar_numero(ond.get("frequencia_hz"), f"TENTACULOS.{nome}.freq") <= 0:
            raise ErroPersistenciaAnimacao(f"Frequência inválida em '{nome}'.")


def _validar_reacoes(reacoes: Any) -> None:
    if not isinstance(reacoes, dict):
        raise ErroPersistenciaAnimacao("'REACOES' deve ser dict.")
    for nome, dur in reacoes.get("duracoes", {}).items():
        if _validar_numero(dur, f"REACOES.duracoes.{nome}") < 0.0:
            raise ErroPersistenciaAnimacao(f"Duração negativa em REACOES.{nome}.")
    aceno = reacoes.get("aceno", {})
    if "duracao_s" in aceno and _validar_numero(aceno["duracao_s"], "aceno.dur") <= 0:
        raise ErroPersistenciaAnimacao("Duração de aceno deve ser > 0.")


def _validar_vfx(vfx: Any) -> None:
    if not isinstance(vfx, dict):
        raise ErroPersistenciaAnimacao("'VFX' deve ser dict.")
    for nome, spec in vfx.items():
        ancora = str(spec.get("ancora", ""))
        if not ancora_vfx_valida(ancora):
            raise ErroPersistenciaAnimacao(f"Âncora inválida '{ancora}' em VFX.{nome}.")
        dur = _validar_numero(spec.get("duracao_s"), f"VFX.{nome}.duracao_s")
        escala = _validar_numero(spec.get("escala"), f"VFX.{nome}.escala")
        if dur < 0.0 or escala <= 0.0:
            raise ErroPersistenciaAnimacao(f"Parâmetros inválidos em VFX.{nome}.")
        _validar_trio(spec.get("deslocamento", (0.0, 0.0, 0.0)), f"VFX.{nome}.desloc")
        cor = spec.get("cor", (1.0, 1.0, 1.0, 1.0))
        if not isinstance(cor, (tuple, list)) or len(cor) != 4:
            raise ErroPersistenciaAnimacao(f"Cor inválida em VFX.{nome}.")
        for idx, c in enumerate(cor):
            val = _validar_numero(c, f"VFX.{nome}.cor[{idx}]")
            if val < 0.0 or val > 1.0:
                raise ErroPersistenciaAnimacao(f"Canal de cor fora [0,1] em VFX.{nome}.")


def _validar_gltf(gltf_clips: Any) -> None:
    if not isinstance(gltf_clips, dict):
        raise ErroPersistenciaAnimacao("'CLIPES_GLTF' deve ser dict.")
    for nome, cfg in gltf_clips.items():
        ini = _validar_numero(cfg.get("inicio_s", 0.0), f"CLIPES_GLTF.{nome}.inicio")
        fim = cfg.get("fim_s")
        vel = _validar_numero(cfg.get("velocidade", 1.0), f"CLIPES_GLTF.{nome}.vel")
        peso = _validar_numero(cfg.get("peso_mistura", 1.0), f"CLIPES_GLTF.{nome}.peso")
        if ini < 0.0 or vel <= 0.0 or not (0.0 <= peso <= 1.0):
            raise ErroPersistenciaAnimacao(f"Configuração glTF inválida em '{nome}'.")
        if fim is not None and _validar_numero(fim, f"CLIPES_GLTF.{nome}.fim") <= ini:
            raise ErroPersistenciaAnimacao(f"Recorte inválido em '{nome}': {ini}..{fim}.")


def validar_dados_animacao(dados: dict[str, Any]) -> None:
    """Valida todas as famílias, nós, âncoras, tempos e limites de ``animation.py``."""
    for chave in TOP_LEVEL_KEYS:
        if chave not in dados:
            raise ErroPersistenciaAnimacao(f"Seção obrigatória ausente: '{chave}'.")
    idle_clips = dados["IDLE_CLIPS"]
    if not isinstance(idle_clips, dict):
        raise ErroPersistenciaAnimacao("'IDLE_CLIPS' deve ser dict.")
    for nome, clipe in idle_clips.items():
        _validar_bloco_trilhas(clipe, f"IDLE_CLIPS.{nome}")
        if "deslocamento_corpo" in clipe:
            _validar_trio(clipe["deslocamento_corpo"], f"IDLE_CLIPS.{nome}.deslocamento_corpo")
    _validar_cenas_idle(dados["CENAS_IDLE"])
    for nome, clipe in dados["LOCOMOCAO_CLIPS"].items():
        _validar_bloco_trilhas(clipe, f"LOCOMOCAO_CLIPS.{nome}")
    _validar_respiracao(dados["RESPIRACAO"])
    _validar_danca(dados["DANCA"])
    _validar_tentaculos(dados["TENTACULOS"])
    _validar_reacoes(dados["REACOES"])
    _validar_vfx(dados["VFX"])
    _validar_gltf(dados["CLIPES_GLTF"])


def _eh_import_permitido(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.ImportFrom):
        return False
    if stmt.module == "__future__":
        return True
    return stmt.module == "typing" and all(a.name == "Any" for a in stmt.names)


def _eh_docstring(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _extrair_atribuicao(stmt: ast.stmt) -> tuple[str, ast.expr] | None:
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
        alvo = stmt.targets[0]
        if isinstance(alvo, ast.Name):
            return alvo.id, stmt.value
    elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        if stmt.value is not None:
            return stmt.target.id, stmt.value
    return None


def parse_texto_animation(texto: str) -> dict[str, Any]:
    """Lê literais de topo de ``animation.py`` por AST sem executar código."""
    try:
        arvore = ast.parse(texto)
    except SyntaxError as exc:
        raise ErroPersistenciaAnimacao(f"Erro de sintaxe: {exc}") from exc

    dados: dict[str, Any] = {}
    permitidos = set(TOP_LEVEL_KEYS)
    for idx, stmt in enumerate(arvore.body):
        if idx == 0 and _eh_docstring(stmt):
            continue
        if _eh_import_permitido(stmt):
            continue
        par = _extrair_atribuicao(stmt)
        if par is None or par[0] not in permitidos:
            raise ErroPersistenciaAnimacao(
                f"Declaração não suportada na linha {stmt.lineno} de animation.py."
            )
        nome, expr = par
        try:
            dados[nome] = ast.literal_eval(expr)
        except (ValueError, SyntaxError) as exc:
            raise ErroPersistenciaAnimacao(
                f"Valor não literal em '{nome}' (linha {stmt.lineno})."
            ) from exc

    validar_dados_animacao(dados)
    return dados


def _norm_float(valor: float) -> str:
    if math.isclose(valor, 0.0, abs_tol=1e-9):
        return "0.0"
    arred = round(valor, 6)
    return repr(arred)


def _escapar_str(texto: str) -> str:
    escapado = texto.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escapado}"'


def _formatar_colecao_inline(valor: tuple[Any, ...] | list[Any] | dict[Any, Any]) -> str:
    if isinstance(valor, tuple):
        if not valor:
            return "()"
        corpo = ", ".join(_formatar_inline(item) for item in valor)
        return f"({corpo},)" if len(valor) == 1 else f"({corpo})"
    if isinstance(valor, list):
        corpo = ", ".join(_formatar_inline(item) for item in valor)
        return f"[{corpo}]"
    if not valor:
        return "{}"
    itens = [
        f"{_formatar_inline(k)}: {_formatar_inline(v)}"
        for k, v in _ordenar_itens_dict(valor)
    ]
    return "{" + ", ".join(itens) + "}"


def _formatar_inline(valor: Any) -> str:
    if isinstance(valor, bool):
        return "True" if valor else "False"
    if isinstance(valor, int):
        return repr(valor)
    if isinstance(valor, float):
        return _norm_float(valor)
    if isinstance(valor, str):
        return _escapar_str(valor)
    if valor is None:
        return "None"
    if isinstance(valor, (tuple, list, dict)):
        return _formatar_colecao_inline(valor)
    raise PersistenciaAnimacaoError(f"Tipo não serializável: {type(valor)!r}")


def _chave_ordenacao(par: tuple[Any, Any]) -> tuple[int, str]:
    k = par[0]
    return (0 if isinstance(k, int) else 1, f"{k:09d}" if isinstance(k, int) else str(k))


def _ordenar_itens_dict(dicionario: dict[Any, Any]) -> Iterable[tuple[Any, Any]]:
    return sorted(dicionario.items(), key=_chave_ordenacao)


def _formatar_literal(valor: Any, indent: int = 0) -> str:
    inline = _formatar_inline(valor)
    if indent * 4 + len(inline) <= 78 or not isinstance(valor, (dict, tuple, list)):
        return inline
    pad = "    " * (indent + 1)
    fecha_pad = "    " * indent
    if isinstance(valor, dict):
        linhas = [
            f"{pad}{_formatar_inline(k)}: {_formatar_literal(v, indent + 1)},"
            for k, v in _ordenar_itens_dict(valor)
        ]
        return "{\n" + "\n".join(linhas) + f"\n{fecha_pad}}}"
    abra, fecha = ("(", ")") if isinstance(valor, tuple) else ("[", "]")
    linhas = [f"{pad}{_formatar_literal(item, indent + 1)}," for item in valor]
    return f"{abra}\n" + "\n".join(linhas) + f"\n{fecha_pad}{fecha}"


def serializar_dados_animacao(dados: dict[str, Any]) -> str:
    """Serializa ``dados`` validados em código Python determinístico e legível."""
    validar_dados_animacao(dados)
    cabecalho = (
        '"""Dados autorais canônicos do Mário editados diretamente pelo editor.\n\n'
        "Domínio puro (sem Panda3D, Qt ou Win32). Chaves e itens ordenados de forma\n"
        "determinística para manter diffs limpos no Git.\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        "from typing import Any\n"
    )
    blocos = [cabecalho]
    for chave in TOP_LEVEL_KEYS:
        valor = dados[chave]
        anotacao = ": dict[str, Any]" if isinstance(valor, dict) else ": int"
        corpo = _formatar_literal(valor, indent=0)
        blocos.append(f"\n{chave}{anotacao} = {corpo}\n")
    return "".join(blocos)


def carregar_arquivo_animacao(
    caminho: Path | None = None,
) -> ArquivoAnimacao:
    """Carrega, valida e assina o arquivo ``animation.py`` em disco."""
    alvo = caminho or CAMINHO_ANIMATION_PADRAO
    texto = alvo.read_text(encoding="utf-8")
    stat = alvo.stat()
    dados = parse_texto_animation(texto)
    return ArquivoAnimacao(
        caminho=alvo,
        dados=dados,
        sha256=sha256_texto(texto),
        mtime_ns=stat.st_mtime_ns,
    )


def salvar_arquivo_animacao(
    caminho: Path | None,
    dados: dict[str, Any],
    *,
    sha256_esperado: str | None = None,
    forcar: bool = False,
) -> ArquivoAnimacao:
    """Valida, verifica conflitos e grava ``animation.py`` atomicamente."""
    alvo = caminho or CAMINHO_ANIMATION_PADRAO
    if sha256_esperado is not None and not forcar and alvo.is_file():
        sha_atual = sha256_texto(alvo.read_text(encoding="utf-8"))
        if sha_atual != sha256_esperado:
            raise ConflitoArquivoExterno(sha256_esperado, sha_atual)

    conteudo = serializar_dados_animacao(dados)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_nome = tempfile.mkstemp(
        dir=str(alvo.parent),
        prefix=".animation.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_nome)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(conteudo)
            handle.flush()
            os.fsync(handle.fileno())
        parse_texto_animation(tmp_path.read_text(encoding="utf-8"))
        os.replace(tmp_path, alvo)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    stat = alvo.stat()
    return ArquivoAnimacao(
        caminho=alvo,
        dados=dados,
        sha256=sha256_texto(conteudo),
        mtime_ns=stat.st_mtime_ns,
    )
