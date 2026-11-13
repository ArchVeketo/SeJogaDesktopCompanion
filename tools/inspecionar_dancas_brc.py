"""Lê metadados de dança da instalação Steam para o estudo de retargeting.

Requer UnityPy 1.25.4 no Python usado para a análise. Não exporta curvas.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

BUNDLES = {
    "mocap_animation": {"popping"},
    "mocap_animation_two": {
        "breaking",
        "BreakingLoop",
        "housedance",
        "housedanceLoop",
        "hiphop",
        "hiphopLoop",
        "locking",
        "toprock",
    },
}


def _resumir_clipe(objeto):
    clip = objeto.read_typetree()
    muscle = clip["m_MuscleClip"]
    dados = muscle["m_Clip"]["data"]
    dense = dados["m_DenseClip"]
    frames = dense["m_FrameCount"]
    canais = dense["m_CurveCount"]
    if frames * canais != len(dense["m_SampleArray"]):
        raise ValueError(f"dimensões inconsistentes em {clip['m_Name']}")
    bindings = Counter(
        f"{b['typeID']}/{b['customType']}"
        for b in clip["m_ClipBindingConstant"]["genericBindings"]
    )
    return {
        "path_id": objeto.path_id,
        "duracao_s": muscle["m_StopTime"] - muscle["m_StartTime"],
        "loop": muscle["m_LoopTime"],
        "hz": dense["m_SampleRate"],
        "frames_densos": frames,
        "canais_densos": canais,
        "canais_streamed": dados["m_StreamedClip"]["curveCount"],
        "canais_constantes": len(dados["m_ConstantClip"]["data"]),
        "curvas_rotacao": len(clip["m_RotationCurves"]),
        "bindings_tipo_subtipo": dict(bindings),
    }


def main():
    """Emite a estrutura dos clipes sem copiar amostras do jogo."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dados", type=Path, help="Pasta Bomb Rush Cyberfunk_Data")
    args = parser.parse_args()
    assets = args.dados / "StreamingAssets" / "Assets"
    for bundle in BUNDLES:
        if not (assets / bundle).is_file():
            parser.error(f"bundle ausente: {assets / bundle}")
    try:
        import UnityPy
    except ImportError as exc:
        parser.exit(1, f"UnityPy indisponível no Python de análise: {exc}\n")

    relatorio = {}
    for bundle, esperados in BUNDLES.items():
        objetos = UnityPy.load(str(assets / bundle)).objects
        clipes = {}
        for objeto in objetos:
            if objeto.type.name != "AnimationClip":
                continue
            nome = objeto.peek_name()
            if nome in esperados:
                clipes[nome] = _resumir_clipe(objeto)
        if esperados - clipes.keys():
            parser.error(
                f"clipes ausentes em {bundle}: {sorted(esperados - clipes.keys())}"
            )
        relatorio[bundle] = {
            "avatares": sorted(
                o.peek_name() for o in objetos if o.type.name == "Avatar"
            ),
            "clipes": clipes,
        }
    print(json.dumps(relatorio, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
