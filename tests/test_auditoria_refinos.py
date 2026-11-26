"""Regressões direcionadas aos refinos de física, música, UI, animação e empacotamento."""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest


def test_physics_cancel_midair_restores_gravity_nan_guards_and_cleanup():
    from sejoga.configuracao import Settings
    from sejoga.desktop.fisica import MAX_VELOCITY, ScreenSpacePhysics

    cfg = Settings()
    cfg.physics.collide_with_windows = False
    cfg.physics.wall_thickness = 5
    p = ScreenSpacePhysics(screen_width=1000, screen_height=800, settings=cfg)
    assert p._wall_thickness == 5.0

    # Com gravidade previamente ativa, cancelar arraste no ar não pode desligar a gravidade.
    p.set_position(300, 200)
    p.set_gravity(True)
    p.start_drag(300, 200)
    p.update_drag(300, 250)
    assert p.end_drag(cancel=True) == (0, 0)
    assert p.state.gravity_active is True
    assert p.body.mass == pytest.approx(cfg.physics.mass)

    # Entradas não-finitas nunca propagam NaN/Inf.
    p.apply_impulse((float("nan"), 100.0))
    p.set_position(float("nan"), 200.0)
    p.step(float("inf"))
    assert all(np.isfinite(v) for v in p.state.position)
    assert np.hypot(*p.state.velocity) <= MAX_VELOCITY + 1e-6

    # cleanup remove corpo, forma do mascote e TODAS as arestas da tela.
    p.cleanup()
    assert len(p.space.bodies) == 0
    assert len(p.space.shapes) == 0


def test_extrair_paleta_album_e_cyber_ink_vivo():
    from PIL import Image

    from sejoga.musica.escuta_musica import extrair_paleta_album
    from sejoga.render.dinamica_contorno import cor_contorno_viva

    assert extrair_paleta_album(b"") == ()
    assert extrair_paleta_album(b"not-an-image") == ()

    img = Image.new("RGB", (32, 32), (255, 130, 18))
    for y in range(16, 32):
        for x in range(16, 32):
            img.putpixel((x, y), (24, 210, 245))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    paleta = extrair_paleta_album(buf.getvalue())
    assert len(paleta) >= 1
    assert all(0.0 <= c <= 1.0 for rgb in paleta for c in rgb)

    # Idle em repouso absoluto mantém a cor exata escolhida pelo usuário.
    base = (0.0, 1.0, 0.0)
    assert cor_contorno_viva(base, "idle") == base

    # Durante dança com paleta de álbum, contorno pulsa em direção ao sotaque do álbum.
    viva = cor_contorno_viva(base, "dance", bass=0.65, album_rgb=paleta[0])
    assert viva != base


def test_smtc_identidade_propriedades_nulas_e_silencio_ritmo():
    from sejoga.configuracao import MusicSettings
    from sejoga.musica.analisador_ritmo import AnalisadorRitmo
    from sejoga.musica.escuta_musica import MusicListener

    assert MusicListener._identidade_sessao(None) is None
    assert MusicListener._identidade_sessao(
        SimpleNamespace(source_app_user_model_id="Spotify.exe")
    ) == "Spotify.exe"

    publicados: list[object] = []
    listener = MusicListener(MusicSettings(), on_update=publicados.append)

    class SessaoSemProps:
        source_app_user_model_id = "AppMusica"

        @staticmethod
        def get_playback_info():
            return SimpleNamespace(playback_status="Playing")

        @staticmethod
        async def try_get_media_properties_async():
            return None

    asyncio.run(listener._publicar_sessao_smtc(SessaoSemProps(), "Playing"))
    assert publicados[-1].is_playing is True
    assert publicados[-1].source_app_id == "AppMusica"

    from sejoga.musica.classificador_midia import decidir_musica_ativa

    analisador = AnalisadorRitmo(sample_rate=48_000, hop_size=512, window_size=2048)
    silencio = np.zeros((512, 2), dtype=np.float32)
    for i in range(10):
        frame = analisador.processar_bloco(silencio, now=1.0 + i * 0.01, smtc_playing=True)
    assert frame.music_active is False
    ativo, conf = decidir_musica_ativa(
        "media_session",
        "music_app",
        True,
        audio_active=False,
        audio_level=0.0,
        music_confidence=0.0,
    )
    assert (ativo, conf) == (True, 0.9)


def _criar_dialogo_teste(tmp_path, monkeypatch, personalidade: str = "brc_malandro"):
    from sejoga import configuracao
    from sejoga.desktop import inicializacao_automatica, interface
    from sejoga.desktop.interface import SettingsDialog

    destino = tmp_path / "cfg_refinos.toml"
    monkeypatch.setenv("SEJOGA_CONFIG_PATH", str(destino))
    monkeypatch.setattr(configuracao, "default_config_path", lambda: destino)
    monkeypatch.setattr(interface, "default_config_path", lambda: destino)
    monkeypatch.setattr(inicializacao_automatica, "esta_ativo", lambda: False)
    monkeypatch.setattr(inicializacao_automatica, "desativar", lambda: True)

    cfg = configuracao.Settings()
    cfg.behavior.idle_personality = personalidade
    cfg.behavior.wander = False
    cfg.behavior.react_to_attention = False
    cfg.behavior.sleep_after_idle_seconds = 120
    cfg.audio.enabled = False
    cfg.audio.master_volume = 0.35
    cfg.music.source = "off"
    return SettingsDialog(cfg)


def test_settings_dialog_brc_stance_audio_e_music_enabled(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    dlg = _criar_dialogo_teste(tmp_path, monkeypatch)
    assert dlg.personality_input.currentData() == "brc_malandro"
    assert not dlg.wander_input.isChecked()
    assert not dlg.react_attention_input.isChecked()
    assert dlg.sleep_idle_input.value() == 120
    assert not dlg.audio_enabled_input.isChecked()
    assert dlg.master_volume_input.value() == pytest.approx(0.35)

    updates = []
    dlg.settings_applied.connect(updates.append)
    dlg._save()
    assert updates[0].music.enabled is False
    assert updates[0].behavior.idle_personality == "brc_malandro"
    assert updates[0].behavior.wander is False
    assert updates[0].behavior.react_to_attention is False
    assert updates[0].behavior.sleep_after_idle_seconds == 120
    assert updates[0].audio.enabled is False
    assert updates[0].audio.master_volume == pytest.approx(0.35)
    dlg.close()


def test_controlador_preview_restore_e_espirro():
    from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
    from sejoga.nucleo.esqueleto import Rig
    from sejoga.nucleo.modelo import load_model
    from sejoga.nucleo.recursos import resolve_model

    rig = Rig.from_model(load_model(resolve_model()))
    ctrl = AnimationController(rig)
    ctrl.dance_motion.override = "hip_hop"
    ctrl.preview_dance("cyber_skank")
    assert ctrl.dance_motion.override == "cyber_skank"
    ctrl.update(0.1)
    assert ctrl.state == AnimationState.DANCE
    ctrl._dance_preview_remaining = 0.05
    ctrl.update(0.1)
    assert ctrl.dance_motion.override == "hip_hop"

    ctrl2 = AnimationController(rig)
    ctrl2.set_idle_personality("calm")
    with patch.object(ctrl2.agencia, "atualizar"):
        ctrl2.update(0.05, music_playing=False, grounded=True)
        ctrl2.idle_time = 20.0
        ctrl2._cooldowns.clear()
        ctrl2._proximo_espirro_em = ctrl2.clock + 0.01
        ctrl2.update(0.05, music_playing=False, grounded=True)
    assert ctrl2._reaction == AnimationState.SNEEZE


def test_editor_acoes_mixamo_e_teleporte():
    from sejoga.editor.catalogo import construir_catalogo
    from sejoga.editor.documento import DocumentoEditor
    from sejoga.editor.sessao_previa import ModoPrevia, SessaoPrevia

    doc = DocumentoEditor()
    sess = SessaoPrevia(doc)
    por_id = {a.id: a for a in construir_catalogo(doc.rascunho)}
    for acao_id in (
        "danca:clipe:arm_stretching",
        "reacoes:entradas:goku_teleport_in",
        "reacoes:saidas:goku_teleport_out",
    ):
        if acao_id in por_id:
            sess.definir_modo(ModoPrevia.TOMADA)
            sess.selecionar_acao(por_id[acao_id])
            assert sess.ir_para(0.4).pose


def test_build_ps1_portavel_sem_caminho_fixo_usuario():
    script_text = (Path(__file__).resolve().parents[1] / "build.ps1").read_text(
        encoding="utf-8"
    )
    assert "C:/Users/" not in script_text
    assert "C:\\Users\\" not in script_text
    assert "panda3d.__file__" in script_text
    assert "CodexPrimaryRuntime" in script_text


def test_mouse_buttons_sem_hwnd_inicializado_nao_falha(monkeypatch):
    pytest.importorskip("PySide6")
    from sejoga.render import janela

    monkeypatch.setattr(janela.win32gui, "GetCapture", lambda: 0)
    monkeypatch.setattr(janela.win32api, "GetAsyncKeyState", lambda _key: 0)

    app = janela.OverlayApp.__new__(janela.OverlayApp)
    app._native_buttons = set()
    assert app._mouse_buttons() == frozenset()

    app.hwnd = 0
    app._capture_held = True
    app._drag_active = False
    app._native_buttons = {"right"}
    res = app._mouse_buttons()
    assert res == frozenset()
    assert "right" not in app._native_buttons
    assert app._capture_held is False


def test_estilos_vfx_sete_presets_distintos_e_seguros_chroma():
    from sejoga.render.chroma_tuning import derivar_chroma, pixel_e_chroma
    from sejoga.render.estilos_vfx import construir_quadros_estilo_rgba

    presets = (
        "pb_escuro",
        "pb_claro",
        "colorido",
        "hifi_rush",
        "spider_verse",
        "anime_sakuga",
        "lowpoly_3d",
    )
    chroma_cfg = derivar_chroma("#FF00FF")
    assinaturas: dict[str, bytes] = {}
    for preset in presets:
        quadros = construir_quadros_estilo_rgba("impacto", preset)
        assert len(quadros) == 4
        q1 = quadros[1]
        assert q1.shape == (256, 256, 4)
        assert set(np.unique(q1[..., 3]).tolist()).issubset({0, 255})
        assert np.any(q1[..., 3] == 255)
        opacos = q1[q1[..., 3] == 255]
        for px in opacos[::32]:
            assert not pixel_e_chroma((int(px[0]), int(px[1]), int(px[2])), chroma_cfg)
        assinaturas[preset] = q1.tobytes()

    assert len(set(assinaturas.values())) == len(presets)


def test_celebrate_punhos_fechados_e_maos_longe_dos_fones():
    import math

    from sejoga.animacao.gestos_dedos import PEGADAS
    from sejoga.animacao.poses_base import pose_interaction
    from sejoga.nucleo.cinematica import posicao_no
    from sejoga.nucleo.esqueleto import Rig
    from sejoga.nucleo.modelo import load_model
    from sejoga.nucleo.recursos import resolve_model

    assert PEGADAS["celebrate"] == 1.0
    m = load_model(resolve_model())
    rig = Rig.from_model(m)
    for step in range(21):
        t = step * 0.1
        rig.reset()
        pose_interaction(rig, "celebrate", t)
        pose = rig.pose()
        d_r = math.dist(posicao_no(m, "hand", pose), posicao_no(m, "fone-direito", pose))
        d_l = math.dist(posicao_no(m, "hand2", pose), posicao_no(m, "fone-esquerdo", pose))
        assert d_r >= 0.14
        assert d_l >= 0.14


def test_palco_fnf_speakers_estrutura_e_altura():
    import json

    gltf_path = Path(__file__).resolve().parents[1] / "assets" / "model" / "Boomboxes.gltf"
    doc = json.loads(gltf_path.read_text(encoding="utf-8"))
    assert doc["asset"]["generator"] == "SeJogaDesktopCompanion-fnf-stage-speakers"
    nomes = {no.get("name", "") for no in doc["nodes"]}
    for obrigatorio in (
        "Caixa de som meio",
        "Caixa de som esquerda",
        "Caixa de som direita",
        "Cone_meio_0",
        "Calota_meio_0",
    ):
        assert obrigatorio in nomes


def test_filtros_visuais_cinco_canonicos_e_migracao_legado():
    from sejoga.configuracao import WindowSettings

    filtros = ("blockbench", "street", "anime", "spiderverse", "holograma")
    for filtro in filtros:
        assert WindowSettings(visual_filter=filtro).visual_filter == filtro

    assert WindowSettings().visual_filter == "blockbench"
    assert WindowSettings(visual_filter="anime_impact").visual_filter == "anime"
    assert WindowSettings(visual_filter="padrao").visual_filter == "street"
    assert WindowSettings(visual_filter="hifi_comic").visual_filter == "street"
    assert WindowSettings(visual_filter="rascunho").visual_filter == "spiderverse"
    assert WindowSettings(visual_filter="gameboy").visual_filter == "blockbench"


def test_estilos_vfx_formas_distintas_e_malhas_3d():
    from sejoga.render.chroma_tuning import derivar_chroma, pixel_e_chroma
    from sejoga.render.estilos_vfx import construir_quadros_estilo_rgba

    presets = (
        "pb_escuro",
        "pb_claro",
        "colorido",
        "hifi_rush",
        "spider_verse",
        "anime_sakuga",
        "lowpoly_3d",
    )
    chroma_cfg = derivar_chroma("#FF00FF")
    for nome in ("impacto", "musica", "susto", "assinatura"):
        assinaturas: dict[str, bytes] = {}
        for preset in presets:
            quadros = construir_quadros_estilo_rgba(nome, preset)
            assert len(quadros) == 4
            q1 = quadros[1]
            assert q1.shape == (256, 256, 4)
            assert set(np.unique(q1[..., 3]).tolist()).issubset({0, 255})
            assert np.any(q1[..., 3] == 255)
            opacos = q1[q1[..., 3] == 255]
            for px in opacos[::32]:
                assert not pixel_e_chroma((int(px[0]), int(px[1]), int(px[2])), chroma_cfg)
            assinaturas[preset] = q1.tobytes()

        assert len(set(assinaturas.values())) == len(presets)


    # Regra do projeto: pré-carregar Qt antes de importar Panda3D na mesma sessão pytest.
    from PySide6 import QtCore  # noqa: F401

    from sejoga.render.efeitos_street import construir_malha_vfx_3d

    for nome in ("impacto", "musica", "queda_chao"):
        no = construir_malha_vfx_3d(nome)
        nos_geom = [
            np.node() for np in [no, *no.findAllMatches("**/+GeomNode")] if np.node().isGeomNode()
        ]
        assert len(nos_geom) >= 1
        assert any(g.getNumGeoms() >= 1 for g in nos_geom)


def test_dancas_padrao_head_bob_hip_hop_rock_fk_e_amplitude():
    import math

    from sejoga.animacao.movimento_danca import DanceMotion
    from sejoga.nucleo.cinematica import posicao_no
    from sejoga.nucleo.esqueleto import Rig
    from sejoga.nucleo.modelo import load_model
    from sejoga.nucleo.recursos import resolve_model

    modelo = load_model(resolve_model())
    rig = Rig.from_model(modelo)

    for estilo in ("head_bob", "hip_hop", "rock"):
        dm = DanceMotion()
        dm.override = dm.style = estilo
        dm.tempo = 108.0
        dm.energy = 0.65
        dm.bass = 0.45
        dm.strength = 1.0

        head_x: list[float] = []
        dist_min = float("inf")
        for k in range(32):
            dm.phase = (k / 8.0) * math.tau
            dm.style_beats = k / 8.0
            rig.reset()
            dm.apply(rig)
            pose = rig.pose()
            head_x.append(math.degrees(pose["head"].x))
            for mao, fone in (("hand", "fone-direito"), ("hand2", "fone-esquerdo")):
                dist_min = min(
                    dist_min,
                    math.dist(posicao_no(modelo, mao, pose), posicao_no(modelo, fone, pose)),
                )

        assert dist_min >= 0.14, f"{estilo}: distancia minima mao-fone={dist_min:.4f}"
        assert min(head_x) < -10.0, f"{estilo}: head_x minimo={min(head_x):.2f}"
        assert max(head_x) > 2.0, f"{estilo}: head_x maximo={max(head_x):.2f}"


def _validar_malha_vfx_e_cores(no, chroma_cfg) -> None:
    import math

    from panda3d.core import GeomVertexReader

    from sejoga.render.chroma_tuning import pixel_e_chroma

    nos_geom = [
        np.node() for np in [no, *no.findAllMatches("**/+GeomNode")] if np.node().isGeomNode()
    ]
    assert len(nos_geom) >= 1
    assert any(gn.getNumGeoms() >= 1 for gn in nos_geom)
    for gn in nos_geom:
        for gi in range(gn.getNumGeoms()):
            vdata = gn.getGeom(gi).getVertexData()
            vr = GeomVertexReader(vdata, "vertex")
            cr = GeomVertexReader(vdata, "color")
            while not vr.isAtEnd():
                pt = vr.getData3()
                assert math.isfinite(pt.x) and math.isfinite(pt.y) and math.isfinite(pt.z)
                col = cr.getData4()
                rgb = tuple(
                    min(255, max(0, round((max(0.0, float(c)) ** (1.0 / 1.85)) * 255.0)))
                    for c in (col.x, col.y, col.z)
                )
                assert not pixel_e_chroma(rgb, chroma_cfg)


def test_vfx_sete_estilos_coreografias_3d_distintas_e_seguras_chroma():
    # Regra do projeto: carregar PySide6 antes de Panda3D na mesma sessão pytest.
    from PySide6 import QtCore  # noqa: F401

    presets = (
        "pb_escuro",
        "pb_claro",
        "colorido",
        "hifi_rush",
        "spider_verse",
        "anime_sakuga",
        "lowpoly_3d",
    )

    from panda3d.core import NodePath

    from sejoga.render.chroma_tuning import derivar_chroma
    from sejoga.render.efeitos_street import GerenciadorEfeitosStreet
    chroma_cfg = derivar_chroma("#FF00FF")
    assinaturas: dict[str, frozenset[tuple[str, str]]] = {}
    for paleta in presets:
        mgr = GerenciadorEfeitosStreet(NodePath(f"raiz-{paleta}"), paleta=paleta)
        mgr.disparar_impacto_chao(1.3)
        mgr.disparar_carinho()
        mgr.atualizar(
            1 / 60,
            {
                "grounded": True,
                "som_fones": True,
                "dancando": True,
                "acento_danca": True,
                "comemorando": True,
                "choque_argolas": True,
                "tontura": True,
            },
        )
        assert len(mgr._instancias) >= 3
        assinatura = {(inst.tipo_mesh, inst.modo_mov) for inst in mgr._instancias}
        for inst in mgr._instancias:
            if inst.eh_malha_3d:
                _validar_malha_vfx_e_cores(inst.node, chroma_cfg)
        for _ in range(180):
            mgr.atualizar(1 / 60, {"grounded": True})
        assert len(mgr._instancias) == 0
        assinaturas[paleta] = frozenset(assinatura)

    assert len(set(assinaturas.values())) == len(presets)


def _definir_attrs(obj, attrs: dict) -> None:
    for nome, valor in attrs.items():
        setattr(obj, nome, valor)


def _criar_no_caixa_panda3d(root_name: str = "render"):
    from PySide6 import QtCore  # noqa: F401
    # isort: split
    from panda3d.core import CardMaker, NodePath

    root = NodePath(root_name)
    anchor = root.attachNewNode("anchor")
    facing = anchor.attachNewNode("facing")
    susp = facing.attachNewNode("susp")
    squash = susp.attachNewNode("squash")
    model = squash.attachNewNode("model")
    pelvis = model.attachNewNode("pelvis")
    pelvis.setPos(0.0, 0.0, 0.55)

    cm = CardMaker("caixa")
    cm.setFrame(-0.32, 0.32, 0.0, 1.35)
    frente = model.attachNewNode(cm.generate())
    frente.setY(-0.22)
    tras = model.attachNewNode(cm.generate())
    tras.setY(0.22)
    return root, anchor, facing, susp, squash, model, pelvis


def test_pixels_per_unit_reflete_escala_profundidade_e_resize():
    from PySide6 import QtCore  # noqa: F401
    # isort: split
    from panda3d.core import OrthographicLens

    from sejoga.render.renderizador import Panda3DRenderer

    lens = OrthographicLens()
    lens.setFilmSize(2.2, 2.2)

    r = Panda3DRenderer.__new__(Panda3DRenderer)
    _definir_attrs(
        r,
        {
            "width": 480,
            "height": 480,
            "_aspect_ratio": 1.0,
            "_base_bounds_height": 1.5,
            "_model_dimensions": SimpleNamespace(x=1.0, y=1.0, z=1.5),
            "_model_radius_px": 120.0,
            "_view_width": 2.2,
            "_view_height": 2.2,
            "_view_target_z": 0.0,
            "_fit_scale": 1.0,
            "_user_scale": 1.0,
            "_escala_profundidade": 1.0,
            "camera": None,
            "_chroma_filter_quad": None,
            "showbase": SimpleNamespace(
                cam=SimpleNamespace(node=lambda: SimpleNamespace(getLens=lambda: lens)),
                camLens=lens,
                win=None,
            ),
        },
    )

    ppu0 = r.pixels_per_unit
    assert ppu0 == pytest.approx(480.0 / 2.2)
    r._user_scale = 1.4
    assert r.pixels_per_unit == pytest.approx(ppu0 * 1.4)
    r._escala_profundidade = 0.75
    assert r.pixels_per_unit == pytest.approx(ppu0 * 1.4 * 0.75)

    r.resize(960, 720)
    assert r.height == 720
    assert r.pixels_per_unit > ppu0 * 1.4 * 0.75


def _stub_renderer_cinematica(ctrl, *, peso_deitado: float = 0.0):
    from panda3d.core import LVector3f

    from sejoga.render.renderizador import Panda3DRenderer

    root, anchor, facing, susp, squash, model, pelvis = _criar_no_caixa_panda3d()
    r = Panda3DRenderer.__new__(Panda3DRenderer)
    _definir_attrs(
        r,
        {
            "showbase": SimpleNamespace(render=root, animation_controller=ctrl),
            "model_anchor": anchor,
            "_body_facing": facing,
            "_giro_corpo_pivot": (0.0, 0.0, 0.5),
            "_raiz_tilt_rad": 0.0,
            "_suspension_pivot": susp,
            "_squash_pivot": squash,
            "model_np": model,
            "_rig_nodes": {"pelvis": pelvis},
            "lower_body": SimpleNamespace(ground_offset=0.0),
            "music_speaker": SimpleNamespace(
                floor_z=0.0, visibility=0.0, compact=True, jump_progress=0.0, turn=0.0,
            ),
            "_subida_palco": SimpleNamespace(value=0.0, update=lambda *a, **kw: None, step=lambda *a, **kw: None),
            "_assento_palco": SimpleNamespace(value=0.0, update=lambda *a, **kw: None),
            "_posicionar_no_palco": lambda *a, **kw: None,
            "_sono_deitado_peso": peso_deitado,
            "_sono_sentado_peso": 0.0,
            "_breakdance_chao_peso": 0.0,
            "_ultimo_breakdance_pose": (0.0, 0.0),
            "_ultimo_quat_raiz": None,
            "_peso_saida_quat": 0.0,
            "_dz_extra_atual": 0.0,
            "_squash_ref_z": 0.0,
            "_escala_profundidade": 1.0,
            "_profundidade_suave": 0.0,
            "_subida_profundidade": 0.0,
            "_user_scale": 1.0,
            "_fit_scale": 1.0,
            "_model_dimensions": SimpleNamespace(x=0.64, y=0.44, z=1.35),
            "_giro_corpo": SimpleNamespace(angulo=0.0, update=lambda *a, **kw: 0.0),
            "_dance_stage_yaw": SimpleNamespace(value=0.0, update=lambda *a, **kw: None, step=lambda *a, **kw: None),
            "_deslocamento_danca": LVector3f(0.0, 0.0, 0.0),
            "_floor_screen_y": None,
            "pelvis_rest_pos": (0.0, 0.0, 0.55),
            "pelvis_rest_hpr": (0.0, 0.0, 0.0),
            "outline_np": None,
            "_outline_enabled": False,
            "flexible_rig": SimpleNamespace(update=lambda *a, **kw: None, chains=()),
            "_arm_ik": None,
            "_head_pivot": None,
            "_root_pivot": None,
            "pelvis_node": None,
            "squash_stretch": SimpleNamespace(update=lambda *a, **kw: None, scale_x=1.0, scale_y=1.0, scale_z=1.0),
            "_aplicar_squash_stretch": lambda dt=None: None,
            "_atualizar_efeitos_e_argolas": lambda *a, **kw: None,
            "atualizar_sombra_contato": lambda: None,
        },
    )
    return r, anchor, susp, squash, model


def test_anti_afundamento_sono_deitado_e_breakdance(monkeypatch):
    from PySide6 import QtCore  # noqa: F401
    # isort: split
    from panda3d.core import Mat4

    from sejoga.animacao.controlador_animacao import AnimationState

    dance = SimpleNamespace(
        style="breakdance",
        floor_amount=1.0,
        floor_spin=125.0,
        bounce=0.0,
        lean=0.0,
        twist=0.0,
        tilt=0.0,
        energy=0.8,
        strength=1.0,
        phase=0.5,
        bass=0.0,
        deslocamento_emote=(0.0, 0.0),
        dz_pelvis_emote=0.0,
        raiz_quat_emote=None,
    )
    ctrl = SimpleNamespace(
        state=AnimationState.SLEEP,
        modo_sono="deitado",
        state_time=2.5,
        delta_time=1.0 / 60.0,
        raiz_quat_ativa=None,
        dance_motion=dance,
        dz_clipe_ativo=0.0,
        leg_motion=SimpleNamespace(ground_offset=0.0, phase=0.0),
    )

    r, anchor, susp, _squash, model = _stub_renderer_cinematica(ctrl)
    ground = float(model.getTightBounds(anchor)[0].z)
    assert r._posicionar_sono("deitado", peso=1.0) is True
    moved_sleep = float(model.getTightBounds(anchor)[0].z)
    assert moved_sleep >= ground - 1e-3

    # Verifica breakdance procedural invertido mantendo mínimo Z >= ground
    monkeypatch.setattr("sejoga.render.renderizador.carregar_clipe_emote", lambda _style: None)
    r.music_speaker.jump_progress = 1.0
    susp.setMat(Mat4.identMat())
    ctrl.state = AnimationState.DANCE
    motion = SimpleNamespace(
        roll=0.0,
        pitch=0.0,
        yaw=0.0,
        hanging=0.0,
        pendulum_angle=0.0,
        drag_offset=(0.0, 0.0),
        bounce_z=0.0,
    )
    for _ in range(30):
        r.apply_body_motion(motion, grounded=True, dragging=False)
    assert r._breakdance_chao_peso > 0.5
    moved_break = float(model.getTightBounds(anchor)[0].z)
    assert moved_break >= ground - 1e-3


def test_alcance_aereo_sombra_mantem_no_drop_e_zera_alto():
    from PySide6 import QtCore  # noqa: F401

    from sejoga.render.renderizador import Panda3DRenderer

    r = Panda3DRenderer.__new__(Panda3DRenderer)
    r._breakdance_chao_peso = 0.0
    r._height_above_floor_px = 160.0
    r._suspension_pivot = None
    r._anim_air_px_suave = 0.0
    r.model_anchor = None
    r._model_radius_px = 30.0
    r.lower_body = SimpleNamespace(ground_offset=0.0)

    fator_mid = r._alcance_aereo_sombra(None, 1.0 / 60.0, 0.01, SimpleNamespace(z=1.0), 0.0, 0.0)
    assert 0.25 < fator_mid < 0.70

    r._height_above_floor_px = 450.0
    fator_alto = r._alcance_aereo_sombra(None, 1.0 / 60.0, 0.01, SimpleNamespace(z=1.0), 0.0, 0.0)
    assert fator_alto == pytest.approx(0.0)


def test_transicoes_suaves_sono_e_raiz_quat():
    from PySide6 import QtCore  # noqa: F401
    # isort: split
    from panda3d.core import LQuaternionf

    from sejoga.animacao.controlador_animacao import AnimationState

    ctrl_stub = SimpleNamespace(
        state=AnimationState.SLEEP,
        modo_sono="deitado",
        state_time=2.5,
        delta_time=1.0 / 60.0,
        raiz_quat_ativa=LQuaternionf(0.85, 0.35, 0.25, 0.20),
        dance_motion=SimpleNamespace(style="head_bob", floor_amount=0.0, floor_spin=0.0, bounce=0.0, lean=0.0, twist=0.0, tilt=0.0),
        dz_clipe_ativo=0.0,
        leg_motion=SimpleNamespace(ground_offset=0.0),
    )
    r, _anchor, _susp, _squash, _model = _stub_renderer_cinematica(ctrl_stub, peso_deitado=1.0)
    r._aplicar_giro_corpo(1.0 / 60.0, 0.0, None, False)
    assert r._peso_saida_quat == pytest.approx(1.0)

    motion = SimpleNamespace(roll=0.0, pitch=0.0, yaw=0.0, hanging=0.0, pendulum_angle=0.0, drag_offset=(0.0, 0.0), bounce_z=0.0)
    ctrl_stub.state = AnimationState.IDLE
    ctrl_stub.raiz_quat_ativa = None
    r.apply_body_motion(motion, grounded=True, dragging=False)
    assert 0.1 < r._sono_deitado_peso < 0.96
    assert 0.0 < r._peso_saida_quat < 1.0

    for _ in range(90):
        r.apply_body_motion(motion, grounded=True, dragging=False)
    assert r._sono_deitado_peso == pytest.approx(0.0)
    assert r._peso_saida_quat == pytest.approx(0.0)


def test_suavizacao_dz_extra_e_squash_ref():
    from PySide6 import QtCore  # noqa: F401
    # isort: split
    from sejoga.animacao.controlador_animacao import AnimationState
    from sejoga.render.renderizador import Panda3DRenderer

    ctrl_stub = SimpleNamespace(
        state=AnimationState.IDLE,
        modo_sono="em_pe",
        state_time=1.0,
        delta_time=1.0 / 60.0,
        raiz_quat_ativa=None,
        dance_motion=SimpleNamespace(style="head_bob", floor_amount=0.0, floor_spin=0.0, bounce=0.0, lean=0.0, twist=0.0, tilt=0.0),
        dz_clipe_ativo=0.6,
        leg_motion=SimpleNamespace(ground_offset=0.0),
    )
    r, _anchor, _susp, squash, model = _stub_renderer_cinematica(ctrl_stub)
    motion = SimpleNamespace(roll=0.0, pitch=0.0, yaw=0.0, hanging=0.0, pendulum_angle=0.0, drag_offset=(0.0, 0.0), bounce_z=0.0)
    r.apply_body_motion(motion, grounded=True, dragging=False)
    assert 0.0 < r._dz_extra_atual < 0.6

    r2 = Panda3DRenderer.__new__(Panda3DRenderer)
    _definir_attrs(
        r2,
        {
            "model_np": model,
            "_squash_pivot": squash,
            "showbase": SimpleNamespace(
                animation_controller=SimpleNamespace(
                    state=AnimationState.DANCE,
                    dance_motion=SimpleNamespace(style="miku", bounce=0.0, energy=0.0, phase=0.0, strength=0.5, bass=0.0),
                    state_time=0.5,
                    dz_clipe_ativo=0.6,
                    leg_motion=SimpleNamespace(phase=0.0),
                )
            ),
            "_physics_velocity": (0.0, 0.0),
            "_breakdance_chao_peso": 0.0,
            "_sono_deitado_peso": 0.0,
            "_sono_sentado_peso": 0.0,
            "_dz_extra_atual": 0.0,
            "_squash_ref_z": 0.0,
            "_squash_atual": (1.0, 1.0, 1.0),
            "_is_grounded": False,
            "_model_min_z": 0.0,
            "_fit_scale": 1.0,
            "_user_scale": 1.0,
            "_escala_profundidade": 1.0,
            "squash_stretch": SimpleNamespace(scale_x=1.0, scale_y=1.0, scale_z=1.0),
        },
    )
    r2._parametros_squash_stretch = Panda3DRenderer._parametros_squash_stretch.__get__(r2, Panda3DRenderer)
    Panda3DRenderer._aplicar_squash_stretch(r2, 1.0 / 60.0)
    assert 0.0 < r2._squash_ref_z < 0.48


def test_decaimento_tilt_janela_e_regatilho_pet():
    import math
    import time

    from PySide6 import QtCore  # noqa: F401
    # isort: split
    from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
    from sejoga.nucleo.esqueleto import Rig
    from sejoga.nucleo.modelo import load_model
    from sejoga.nucleo.recursos import resolve_model
    from sejoga.render.janela import OverlayApp

    rotacoes: list[float] = []
    st_phys = SimpleNamespace(position=(500.0, 500.0), velocity=(0.0, 0.0), grounded=True, dragging=False)
    app = OverlayApp.__new__(OverlayApp)
    _definir_attrs(
        app,
        {
            "physics": SimpleNamespace(state=st_phys, get_state=lambda: st_phys),
            "renderer": SimpleNamespace(
                model_np=True,
                set_model_screen_position=lambda x, y: None,
                set_model_rotation=lambda *, z=0.0: rotacoes.append(z),
            ),
            "_physics_local": (260.0, 420.0),
            "_drag_active": False,
            "_intro_motion": None,
            "_last_tilt_z": 12.0,
            "_tilt_last_tick": time.perf_counter() - 0.04,
            "_last_model_pos": (260.0, 420.0),
        },
    )
    app._sync_model_with_physics()
    assert app._last_tilt_z is not None and 0.0 < app._last_tilt_z < 12.0
    assert rotacoes and rotacoes[-1] == pytest.approx(app._last_tilt_z)

    ctrl = AnimationController(Rig.from_model(load_model(resolve_model())))
    ctrl.agencia._gerar_desejo_espontaneo = lambda: None
    ctrl.interact("pet")
    for _ in range(15):
        anterior = dict(ctrl.update(1 / 60, grounded=True))
    assert ctrl.state == AnimationState.PET
    ctrl._cooldowns.clear()
    ctrl.interact("pet")
    assert ctrl.pose_resolver._transition_from is not None
    assert ctrl.pose_resolver._state_time == pytest.approx(0.0)
    atual = dict(ctrl.update(1 / 60, grounded=True))
    pior = max(
        math.degrees(max(abs(atual[k].x - anterior[k].x), abs(atual[k].y - anterior[k].y), abs(atual[k].z - anterior[k].z)))
        for k in atual
        if k in anterior
    )
    assert pior < 16.0


def test_gate_atencao_cursor_estacionario_cede_prioridade():
    from sejoga.animacao.foco_atencao import (
        PRIORIDADE_AMBIENTE,
        PRIORIDADE_BORDA,
        GateAtencao,
        GatilhoAtencao,
    )

    gate = GateAtencao()
    gatilhos = [
        GatilhoAtencao("cursor", (220.0, 220.0), 6.0),
        GatilhoAtencao("ambiente", (620.0, 300.0), PRIORIDADE_AMBIENTE),
    ]
    alvo = None
    for _ in range(120):
        alvo = gate.atualizar(
            0.1,
            gatilhos=gatilhos,
            origem_janela=(0.0, 0.0),
            largura=800.0,
            altura=600.0,
        )
    assert gate._cursor_novidade < 0.1
    assert alvo is not None and alvo.fonte == "ambiente"
    assert PRIORIDADE_AMBIENTE < PRIORIDADE_BORDA


def test_respiracao_em_cascata_inclui_antebracos():
    from sejoga.animacao.clipes_ocioso import camada_respiracao
    from sejoga.animacao.respiracao import amostrar_respiracao_cascata

    cascata = amostrar_respiracao_cascata(0.75)
    assert len(cascata) == 4
    assert all(-1.0 <= v <= 1.0 for v in cascata)
    assert len({round(v, 4) for v in cascata}) >= 3

    camada = camada_respiracao(0.8, respiracao_cascata=cascata)
    for grupo in ("body", "head", "right-arm", "left-arm", "ant-arm", "ant-arm2"):
        assert grupo in camada
        rot = camada[grupo]
        assert sum(abs(v) for v in rot) > 1e-5


def test_estado_sit_completo():
    from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
    from sejoga.animacao.estados_delta import delta_sit
    from sejoga.animacao.movimento_pernas import LegMotion
    from sejoga.nucleo.esqueleto import Rig
    from sejoga.nucleo.modelo import load_model
    from sejoga.nucleo.recursos import resolve_model

    ctrl = AnimationController(Rig.from_model(load_model(resolve_model())))
    ctrl.agencia._gerar_desejo_espontaneo = lambda: None
    ctrl.update(0.1)
    ctrl.sentar()
    for _ in range(25):
        ctrl.update(1 / 60, grounded=True)
    assert ctrl.state == AnimationState.SIT
    d_sit = delta_sit(0.8, 0.5, 0.0, 0.3)
    assert d_sit["cintura"].x != 0.0
    assert d_sit["head"].y != 0.0

    lm = LegMotion()
    for i in range(25):
        pose_pernas_sit = lm.update(1 / 60, "sit", time=(i + 1) / 60.0)
    assert abs(pose_pernas_sit.right) > 0.4 or abs(pose_pernas_sit.right_knee) > 0.4

    ctrl.levantar()
    ctrl.update(1 / 60, grounded=True)
    assert ctrl.state == AnimationState.IDLE


def _validar_pulo_fisico() -> None:
    from sejoga.configuracao import Settings
    from sejoga.desktop.fisica import ScreenSpacePhysics

    cfg = Settings()
    cfg.physics.collide_with_windows = False
    phys = ScreenSpacePhysics(screen_width=1200, screen_height=800, settings=cfg)
    phys.set_position(500.0, 800.0 - phys.mascot_radius)
    phys.set_gravity(True)
    for _ in range(15):
        phys.step(1 / 60)
    assert phys.state.grounded is True and phys.jump(vx=120.0, vy_impulse=-680.0) is True
    phys.step(1 / 60)
    assert phys.state.velocity[1] < -300.0
    phys.cleanup()


def test_estado_jump_completo():
    from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
    from sejoga.animacao.estados_delta import delta_jump
    from sejoga.animacao.movimento_pernas import LegMotion
    from sejoga.nucleo.esqueleto import Rig
    from sejoga.nucleo.modelo import load_model
    from sejoga.nucleo.recursos import resolve_model

    d_coil = delta_jump(0.05, (120.0, -400.0))
    d_voo = delta_jump(0.22, (120.0, -400.0))
    assert d_coil["body"].x < 0.0 and d_voo["body"].x > 0.0
    _validar_pulo_fisico()

    ctrl = AnimationController(Rig.from_model(load_model(resolve_model())))
    ctrl.agencia._gerar_desejo_espontaneo = lambda: None
    ctrl.update(0.1)
    ctrl.pular(vx=120.0, vy_impulse=-680.0)
    imp = None
    for _ in range(10):
        ctrl.update(1 / 60, grounded=True, velocity=(0.0, 0.0))
        imp = imp or ctrl.consumir_impulso_pulo()
    assert ctrl.state == AnimationState.JUMP and imp == (120.0, -680.0)
    pose_jump = LegMotion().update(1 / 60, "jump", velocity=(120.0, -500.0), time=0.2)
    assert pose_jump.left_knee != 0.0 or pose_jump.right != 0.0

    for _ in range(18):
        ctrl.update(1 / 60, grounded=False, velocity=(120.0, 140.0))
    assert ctrl.state == AnimationState.FALL




def test_filtro_vfx_troca_ao_vivo_limpa_marcas_e_respeita_desativado():
    from PySide6 import QtCore  # noqa: F401
    # isort: split
    from panda3d.core import CardMaker, NodePath

    from sejoga.catalogos_ui import FILTROS_VISUAIS_UI
    from sejoga.render.efeitos_street import GerenciadorEfeitosStreet

    raiz = NodePath("vfx")
    modelo = raiz.attachNewNode("modelo")
    for nome, x in (("left-feet", -0.5), ("right-feet", 0.5)):
        molde = CardMaker(nome)
        molde.setFrame(-0.15, 0.15, 0, 0.2)
        modelo.attachNewNode(molde.generate()).setX(x)
    mgr = GerenciadorEfeitosStreet(raiz, model_node=modelo)
    tipos_mesh = set()
    anteriores = []
    for filtro, _ in FILTROS_VISUAIS_UI:
        mgr.configurar(filtro=filtro)
        assert all(node.isEmpty() for node in anteriores)
        mgr.disparar_impacto_chao(1.3)
        anteriores = [inst.node for inst in mgr._instancias]
        if filtro == "blockbench":
            assert len(mgr._instancias) == 1
            piloto = mgr._instancias[0]
            assert piloto.tipo_mesh == "impacto_chao_blockbench"
            assert piloto.node.findAllMatches("**/puff_poeira").getNumPaths() == 4
            assert piloto.node.findAllMatches("**/lasca_piso").getNumPaths() == 4
            arco = piloto.node.find("**/arco_01")
            inicio = arco.getPos()
            mgr._atualizar_instancias(.10, {})
            assert arco.getPos() != inicio
            anteriores.append(piloto.referencial_fixo)
            tipos_mesh.add(piloto.tipo_mesh)
            continue
        if filtro in ("street", "anime", "spiderverse", "holograma") and len(mgr._instancias) == 1:
            no_raiz = mgr._instancias[0]
            assert no_raiz.tipo_mesh == f"impacto_chao_{filtro}"
            anteriores.append(no_raiz.referencial_fixo)
            tipos_mesh.add(no_raiz.tipo_mesh)
            continue
        assert len(anteriores) >= 2
        tipos_mesh.add(mgr._instancias[0].tipo_mesh)
    assert len(tipos_mesh) == len(FILTROS_VISUAIS_UI)
    mgr.configurar(habilitado=False)
    mgr.disparar_impacto_chao()
    assert not mgr._instancias
    assert all(node.isEmpty() for node in anteriores)
