"""Sub-inspetores especializados para Respiração, Dança, Tentáculos, Reações, VFX e glTF."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sejoga.editor.esquema import (
    ANCORAS_VFX_VALIDAS,
    GRUPOS_RIG_VALIDOS,
    LIMITES_JUNTA,
)
from sejoga.editor.roteiro import (
    TIPOS_ESTIMULO,
    EstimuloRoteiro,
    ObstaculoPrevia,
    RoteiroEnsaio,
)
from sejoga.editor.widgets_campos import (
    BotaoCorRGBA,
    ConstrutorCamposMixin,
    ListaParesTempoWidget,
    SpinPreciso,
    metadado_campo,
)
from sejoga.nucleo.recursos import assets_dir

_BRAÇOS_PADRAO: tuple[str, ...] = (
    "apoio_caixa",
    "apoio_chao",
    "chifre",
    "colo",
    "contrapeso",
    "cyber_angular",
    "cyber_baixo",
    "dance",
    "graffiti_arco",
    "graffiti_spray",
    "idle",
    "street_attitude",
    "street_solto",
)


def _limpar_layout(layout: QVBoxLayout) -> None:
    while layout.count() > 0:
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def _eh_lista_pares(valor: Any) -> bool:
    if not isinstance(valor, (tuple, list)) or not valor:
        return False
    primeiro = valor[0]
    return isinstance(primeiro, (tuple, list)) and len(primeiro) == 2


def _eh_vetor_numerico(valor: Any) -> bool:
    if not isinstance(valor, (tuple, list)) or not (2 <= len(valor) <= 4):
        return False
    return all(isinstance(v, (int, float)) for v in valor)


class PainelFormularioDict(QWidget):
    """Renderiza e edita um dicionário autorais tipado a partir de um caminho base."""

    campo_editado = Signal(str, object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa o contêiner de campos gerados a partir do dicionário atual."""
        super().__init__(parent)
        self._caminho_base: tuple[Any, ...] = ()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

    def carregar_dicionario(
        self,
        titulo: str,
        dados: dict[str, Any],
        caminho_base: tuple[Any, ...],
        *,
        ignorar: set[str] | None = None,
    ) -> None:
        """Reconstrói os controles do formulário para ``dados`` em ``caminho_base``."""
        _limpar_layout(self._layout)
        self._caminho_base = caminho_base
        ignoradas = ignorar or set()
        grupo = QGroupBox(titulo, self)
        grade = QGridLayout(grupo)
        grade.setColumnStretch(1, 1)
        linha = 0
        for chave in sorted(dados.keys()):
            if chave in ignoradas:
                continue
            valor = dados[chave]
            widget = self._criar_controle_chave(chave, valor, caminho_base)
            if widget is None:
                continue
            meta = metadado_campo(chave)
            grade.addWidget(QLabel(meta.rotulo, grupo), linha, 0)
            grade.addWidget(widget, linha, 1)
            linha += 1
        if linha > 0:
            self._layout.addWidget(grupo)
        else:
            grupo.deleteLater()

    def _criar_controle_chave(
        self,
        chave: str,
        valor: Any,
        caminho_base: tuple[Any, ...],
    ) -> QWidget | None:
        caminho = (*caminho_base, chave)
        if chave == "ancora" and isinstance(valor, str):
            return self._criar_combo_str(
                chave,
                valor,
                sorted(ANCORAS_VFX_VALIDAS),
                caminho,
            )
        if chave == "arquivo" and isinstance(valor, str):
            return self._criar_seletor_gltf(chave, valor, caminho)
        if chave == "fim_s" and (valor is None or isinstance(valor, (int, float))):
            return self._criar_fim_opcional(valor, caminho)
        if chave == "cor" and _eh_vetor_numerico(valor) and len(valor) == 4:
            return self._criar_seletor_cor(valor, caminho)
        if _eh_lista_pares(valor):
            tipo_str = chave == "eventos"
            lista = ListaParesTempoWidget(self, tipo_valor_str=tipo_str)
            lista.definir_itens(tuple((float(t), v) for t, v in valor))
            lista.lista_alterada.connect(
                lambda nova, c=caminho, k=chave: self.campo_editado.emit(
                    f"Editar {k}",
                    c,
                    nova,
                ),
            )
            return lista
        if _eh_vetor_numerico(valor):
            return self._criar_vetor_numerico(chave, valor, caminho)
        if isinstance(valor, dict):
            return self._criar_subgrupo_dict(chave, valor, caminho)
        if isinstance(valor, (bool, int, float)):
            return self._criar_escalar(chave, valor, caminho)
        if isinstance(valor, str):
            rot = QLabel(valor, self)
            rot.setObjectName("rotuloSuave")
            return rot
        return None

    def _criar_escalar(
        self,
        chave: str,
        valor: Any,
        caminho: tuple[Any, ...],
    ) -> QWidget:
        box = QWidget(self)
        grade = QGridLayout(box)
        grade.setContentsMargins(0, 0, 0, 0)
        ctrl = ConstrutorCamposMixin.adicionar_linha_escalar(
            grade,
            0,
            chave,
            valor,
            lambda k, v: self.campo_editado.emit(f"Editar {k}", caminho, v),
        )
        grade.removeWidget(ctrl)
        box.deleteLater()
        ctrl.setParent(self)
        return ctrl

    def _criar_combo_str(
        self,
        chave: str,
        atual: str,
        opcoes: list[str],
        caminho: tuple[Any, ...],
    ) -> QComboBox:
        combo = QComboBox(self)
        itens = list(opcoes)
        if atual not in itens:
            itens.insert(0, atual)
        combo.addItems(itens)
        combo.setCurrentText(atual)
        combo.currentTextChanged.connect(
            lambda txt: self.campo_editado.emit(f"Alterar {chave}", caminho, txt),
        )
        return combo

    def _criar_seletor_gltf(
        self,
        chave: str,
        atual: str,
        caminho: tuple[Any, ...],
    ) -> QWidget:
        box = QWidget(self)
        linha = QHBoxLayout(box)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(4)
        edit = QLineEdit(atual, box)
        edit.editingFinished.connect(
            lambda: self.campo_editado.emit(
                f"Alterar {chave}",
                caminho,
                edit.text().strip(),
            ),
        )
        btn = QPushButton("…", box)
        btn.setFixedWidth(28)
        btn.setToolTip("Escolher arquivo glTF/GLB em assets/")
        btn.clicked.connect(lambda: self._escolher_arquivo_gltf(edit, caminho))
        linha.addWidget(edit, 1)
        linha.addWidget(btn)
        return box

    def _escolher_arquivo_gltf(
        self,
        edit: QLineEdit,
        caminho: tuple[Any, ...],
    ) -> None:
        raiz = assets_dir()
        escolhido, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar clipe glTF/GLB",
            str(raiz),
            "Modelos glTF (*.gltf *.glb)",
        )
        if not escolhido:
            return
        try:
            rel = Path(escolhido).resolve().relative_to(raiz.parent.resolve())
            texto = rel.as_posix()
        except ValueError:
            texto = Path(escolhido).as_posix()
        edit.setText(texto)
        self.campo_editado.emit("Alterar arquivo glTF", caminho, texto)

    def _criar_fim_opcional(
        self,
        valor: float | None,
        caminho: tuple[Any, ...],
    ) -> QWidget:
        box = QWidget(self)
        linha = QHBoxLayout(box)
        linha.setContentsMargins(0, 0, 0, 0)
        chk = QCheckBox("Definido", box)
        chk.setChecked(valor is not None)
        spin = SpinPreciso(
            box,
            minimo=0.0,
            maximo=120.0,
            passo=0.05,
            casas=3,
            unidade=" s",
        )
        spin.definir_valor_silencioso(float(valor) if valor is not None else 2.0)
        spin.setEnabled(valor is not None)
        chk.toggled.connect(
            lambda ativo: self._aplicar_fim_opcional(ativo, spin, caminho),
        )
        spin.valor_confirmado.connect(
            lambda novo: self.campo_editado.emit("Editar fim do clipe", caminho, novo),
        )
        linha.addWidget(chk)
        linha.addWidget(spin, 1)
        return box

    def _aplicar_fim_opcional(
        self,
        ativo: bool,
        spin: SpinPreciso,
        caminho: tuple[Any, ...],
    ) -> None:
        spin.setEnabled(ativo)
        valor: float | None = float(spin.value()) if ativo else None
        self.campo_editado.emit("Alternar fim do clipe", caminho, valor)

    def _criar_seletor_cor(
        self,
        valor: tuple[float, ...],
        caminho: tuple[Any, ...],
    ) -> BotaoCorRGBA:
        seletor = BotaoCorRGBA(self)
        seletor.definir_cor((valor[0], valor[1], valor[2], valor[3]))
        seletor.cor_alterada.connect(
            lambda rgba: self.campo_editado.emit("Editar cor do efeito", caminho, rgba),
        )
        return seletor

    def _criar_vetor_numerico(
        self,
        chave: str,
        valor: tuple[float, ...],
        caminho: tuple[Any, ...],
    ) -> QWidget:
        box = QWidget(self)
        grade = QGridLayout(box)
        grade.setContentsMargins(0, 0, 0, 0)
        grade.setHorizontalSpacing(4)
        grade.setVerticalSpacing(2)
        grade.setColumnStretch(1, 1)
        eixos = ("X", "Y", "Z", "W")
        spins: list[SpinPreciso] = []
        for idx, item in enumerate(valor):
            sp = SpinPreciso(box, minimo=-100.0, maximo=100.0, passo=0.05, casas=3)
            sp.definir_valor_silencioso(float(item))
            spins.append(sp)
            rot = QLabel(eixos[idx] if idx < len(eixos) else f"[{idx}]", box)
            rot.setObjectName("rotuloSuave")
            grade.addWidget(rot, idx, 0)
            grade.addWidget(sp, idx, 1)
            sp.valor_confirmado.connect(
                lambda _v, _i=idx, lst=spins: self.campo_editado.emit(
                    f"Editar {chave}",
                    caminho,
                    tuple(float(s.value()) for s in lst),
                ),
            )
        return box

    def _criar_subgrupo_dict(
        self,
        chave: str,
        dados: dict[str, Any],
        caminho: tuple[Any, ...],
    ) -> QWidget:
        grupo = QGroupBox(chave.replace("_", " ").capitalize(), self)
        grade = QGridLayout(grupo)
        grade.setColumnStretch(1, 1)
        for linha, sub_k in enumerate(sorted(dados.keys())):
            sub_v = dados[sub_k]
            if not isinstance(sub_v, (bool, int, float)):
                continue
            sub_cam = (*caminho, sub_k)
            ConstrutorCamposMixin.adicionar_linha_escalar(
                grade,
                linha,
                sub_k,
                sub_v,
                lambda k, val, sc=sub_cam: self.campo_editado.emit(
                    f"Editar {k}",
                    sc,
                    val,
                ),
            )
        return grupo


class PainelObstaculoTentaculos(QGroupBox):
    """Controles da caixa de obstáculo para ensaio de colisão dos tentáculos."""

    obstaculo_alterado = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa o painel de centro e meia-extensão do obstáculo."""
        super().__init__("Obstáculo de prévia (tentáculos)", parent)
        self._atual = ObstaculoPrevia()
        layout = QVBoxLayout(self)
        self._chk_ativo = QCheckBox("Ativar caixa de obstáculo no viewport", self)
        self._chk_ativo.toggled.connect(self._emitir)
        layout.addWidget(self._chk_ativo)

        self._spins_centro = self._criar_linha_vec("Centro", layout)
        self._spins_ext = self._criar_linha_vec("Meia-ext.", layout)

    def _criar_linha_vec(self, rotulo: str, pai: QVBoxLayout) -> list[SpinPreciso]:
        grade = QGridLayout()
        grade.setHorizontalSpacing(4)
        grade.setVerticalSpacing(2)
        grade.setColumnStretch(1, 1)
        titulo = QLabel(rotulo, self)
        titulo.setObjectName("rotuloSuave")
        grade.addWidget(titulo, 0, 0, 1, 2)
        spins: list[SpinPreciso] = []
        for row_idx, eixo in enumerate(("X", "Y", "Z"), start=1):
            sp = SpinPreciso(self, minimo=-2.0, maximo=2.0, passo=0.02, casas=2)
            sp.valor_confirmado.connect(lambda _v: self._emitir())
            grade.addWidget(QLabel(eixo, self), row_idx, 0)
            grade.addWidget(sp, row_idx, 1)
            spins.append(sp)
        pai.addLayout(grade)
        return spins

    def definir_obstaculo(self, obstaculo: ObstaculoPrevia) -> None:
        """Sincroniza os campos com o ``ObstaculoPrevia`` atual do roteiro."""
        self._atual = obstaculo
        self._chk_ativo.blockSignals(True)
        self._chk_ativo.setChecked(obstaculo.ativo)
        self._chk_ativo.blockSignals(False)
        for sp, val in zip(self._spins_centro, obstaculo.centro, strict=True):
            sp.definir_valor_silencioso(val)
        for sp, val in zip(self._spins_ext, obstaculo.meia_extensao, strict=True):
            sp.definir_valor_silencioso(val)

    def _emitir(self) -> None:
        novo = ObstaculoPrevia(
            ativo=self._chk_ativo.isChecked(),
            centro=(
                float(self._spins_centro[0].value()),
                float(self._spins_centro[1].value()),
                float(self._spins_centro[2].value()),
            ),
            meia_extensao=(
                float(self._spins_ext[0].value()),
                float(self._spins_ext[1].value()),
                float(self._spins_ext[2].value()),
            ),
        )
        self._atual = novo
        self.obstaculo_alterado.emit(novo)


class PainelEstimulosRapidos(QGroupBox):
    """Controles rápidos para ensaiar e agendar estímulos no roteiro."""

    estimulo_disparado = Signal(object)
    estimulo_adicionado = Signal(object)
    roteiro_limpo = Signal()
    modo_sono_alterado = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa seletores de estímulo, instante, modo de sono e ações."""
        super().__init__("Ensaio de reações e roteiro", parent)
        layout = QVBoxLayout(self)
        grid = QGridLayout()
        self._combo_tipo = QComboBox(self)
        self._combo_tipo.addItems(list(TIPOS_ESTIMULO))
        self._spin_tempo = SpinPreciso(
            self,
            minimo=0.0,
            maximo=120.0,
            passo=0.05,
            casas=2,
            unidade=" s",
        )
        self._combo_sono = QComboBox(self)
        self._combo_sono.addItems(["em_pe", "sentado", "deitado"])
        self._combo_sono.currentTextChanged.connect(self.modo_sono_alterado.emit)
        grid.addWidget(QLabel("Estímulo", self), 0, 0)
        grid.addWidget(self._combo_tipo, 0, 1)
        grid.addWidget(QLabel("Instante", self), 1, 0)
        grid.addWidget(self._spin_tempo, 1, 1)
        grid.addWidget(QLabel("Modo sono", self), 2, 0)
        grid.addWidget(self._combo_sono, 2, 1)
        layout.addLayout(grid)
        layout.addLayout(self._criar_botoes())

    def _criar_botoes(self) -> QGridLayout:
        botoes = QGridLayout()
        botoes.setHorizontalSpacing(4)
        botoes.setVerticalSpacing(4)
        btn_agora = QPushButton("Disparar", self)
        btn_agora.setToolTip("Dispara este estímulo imediatamente no viewport")
        btn_agora.clicked.connect(self._on_disparar)
        btn_add = QPushButton("+ Roteiro", self)
        btn_add.setToolTip("Adiciona o estímulo no instante indicado")
        btn_add.clicked.connect(self._on_adicionar)
        btn_limpar = QPushButton("Limpar", self)
        btn_limpar.clicked.connect(self.roteiro_limpo.emit)
        botoes.addWidget(btn_agora, 0, 0)
        botoes.addWidget(btn_add, 0, 1)
        botoes.addWidget(btn_limpar, 1, 0, 1, 2)
        return botoes

    def sincronizar_roteiro(self, roteiro: RoteiroEnsaio, tempo_s: float) -> None:
        """Atualiza o instante sugerido e o modo de sono exibido."""
        self._spin_tempo.definir_valor_silencioso(tempo_s)
        self._combo_sono.blockSignals(True)
        self._combo_sono.setCurrentText(roteiro.modo_sono)
        self._combo_sono.blockSignals(False)

    def _montar_estimulo(self, tempo_s: float) -> EstimuloRoteiro:
        return EstimuloRoteiro(
            tempo_s=tempo_s,
            tipo=self._combo_tipo.currentText(),
            alvo="body",
        )

    def _on_disparar(self) -> None:
        self.estimulo_disparado.emit(
            self._montar_estimulo(float(self._spin_tempo.value())),
        )

    def _on_adicionar(self) -> None:
        self.estimulo_adicionado.emit(
            self._montar_estimulo(float(self._spin_tempo.value())),
        )


class PainelFraseDanca(QWidget):
    """Editor estruturado de frases coreográficas de ``DANCA['frases']``."""

    campo_editado = Signal(str, object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa seletores de passo, acento, poses de braço e juntas do corpo."""
        super().__init__(parent)
        self._chave_frase = ""
        self._dados: dict[str, Any] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._form_topo = PainelFormularioDict(self)
        self._form_topo.campo_editado.connect(self.campo_editado.emit)
        layout.addWidget(self._form_topo)
        layout.addWidget(self._criar_bloco_passos())

    def _criar_bloco_passos(self) -> QGroupBox:
        grupo = QGroupBox("Passos e poses da frase", self)
        vbox = QVBoxLayout(grupo)
        vbox.addLayout(self._criar_grade_passo(grupo))
        vbox.addLayout(self._criar_grade_bracos(grupo))
        vbox.addLayout(self._criar_linha_eixos_pose(grupo))
        return grupo

    def _criar_grade_passo(self, grupo: QWidget) -> QGridLayout:
        grid = QGridLayout()
        self._combo_passo = QComboBox(grupo)
        self._combo_passo.currentIndexChanged.connect(self._atualizar_passo)
        self._spin_acento = SpinPreciso(grupo, minimo=0.0, maximo=2.0, passo=0.05)
        self._spin_acento.valor_confirmado.connect(self._on_acento_mudou)
        self._combo_pose = QComboBox(grupo)
        self._combo_pose.currentIndexChanged.connect(self._atualizar_pose)
        grid.addWidget(QLabel("Passo", grupo), 0, 0)
        grid.addWidget(self._combo_passo, 0, 1)
        grid.addWidget(QLabel("Acento força", grupo), 1, 0)
        grid.addWidget(self._spin_acento, 1, 1)
        grid.addWidget(QLabel("Pose", grupo), 2, 0)
        grid.addWidget(self._combo_pose, 2, 1)
        return grid

    def _criar_grade_bracos(self, grupo: QWidget) -> QGridLayout:
        grid = QGridLayout()
        self._combo_braco_d = QComboBox(grupo)
        self._combo_braco_d.addItems(list(_BRAÇOS_PADRAO))
        self._combo_braco_d.currentTextChanged.connect(
            lambda txt: self._on_braco_mudou("braco_dir", txt),
        )
        self._combo_braco_e = QComboBox(grupo)
        self._combo_braco_e.addItems(list(_BRAÇOS_PADRAO))
        self._combo_braco_e.currentTextChanged.connect(
            lambda txt: self._on_braco_mudou("braco_esq", txt),
        )
        self._combo_junta = QComboBox(grupo)
        self._combo_junta.addItems(sorted(GRUPOS_RIG_VALIDOS))
        self._combo_junta.currentTextChanged.connect(self._atualizar_eixos_junta)
        grid.addWidget(QLabel("Braço direito", grupo), 0, 0)
        grid.addWidget(self._combo_braco_d, 0, 1)
        grid.addWidget(QLabel("Braço esquerdo", grupo), 1, 0)
        grid.addWidget(self._combo_braco_e, 1, 1)
        grid.addWidget(QLabel("Junta corpo", grupo), 2, 0)
        grid.addWidget(self._combo_junta, 2, 1)
        return grid

    def _criar_linha_eixos_pose(self, pai: QWidget) -> QGridLayout:
        grade = QGridLayout()
        grade.setHorizontalSpacing(4)
        grade.setVerticalSpacing(2)
        grade.setColumnStretch(1, 1)
        self._spins_xyz: list[SpinPreciso] = []
        for idx, eixo in enumerate(("X", "Y", "Z")):
            sp = SpinPreciso(
                pai,
                minimo=LIMITES_JUNTA.minimo,
                maximo=LIMITES_JUNTA.maximo,
                passo=1.0,
                casas=2,
                unidade=" °",
            )
            sp.valor_confirmado.connect(lambda _v, _i=idx: self._on_eixo_pose_mudou())
            grade.addWidget(QLabel(eixo, pai), idx, 0)
            grade.addWidget(sp, idx, 1)
            self._spins_xyz.append(sp)
        return grade

    def carregar_frase(self, chave_frase: str, dados: dict[str, Any]) -> None:
        """Carrega os metadados e os passos/poses de ``DANCA['frases'][chave]``."""
        self._chave_frase = chave_frase
        self._dados = dados
        self._form_topo.carregar_dicionario(
            f"Frase: {chave_frase}",
            dados,
            ("DANCA", "frases", chave_frase),
            ignorar={"passos"},
        )
        passos = dados.get("passos", ())
        self._combo_passo.blockSignals(True)
        self._combo_passo.clear()
        for i in range(len(passos)):
            self._combo_passo.addItem(f"Passo {i + 1}", i)
        self._combo_passo.blockSignals(False)
        self._atualizar_passo()

    def _passo_atual(self) -> tuple[int, dict[str, Any]] | None:
        idx = self._combo_passo.currentIndex()
        passos = self._dados.get("passos", ())
        if 0 <= idx < len(passos):
            return idx, passos[idx]
        return None

    def _pose_atual(self) -> tuple[int, int, dict[str, Any]] | None:
        passo = self._passo_atual()
        if passo is None:
            return None
        p_idx, p_dict = passo
        poses = p_dict.get("poses", ())
        pose_idx = self._combo_pose.currentIndex()
        if 0 <= pose_idx < len(poses):
            return p_idx, pose_idx, poses[pose_idx]
        return None

    def _atualizar_passo(self) -> None:
        passo = self._passo_atual()
        self._combo_pose.blockSignals(True)
        self._combo_pose.clear()
        if passo is not None:
            _, p_dict = passo
            self._spin_acento.definir_valor_silencioso(
                float(p_dict.get("acento_forca", 1.0)),
            )
            for j in range(len(p_dict.get("poses", ()))):
                self._combo_pose.addItem(f"Pose {j + 1}", j)
        self._combo_pose.blockSignals(False)
        self._atualizar_pose()

    def _atualizar_pose(self) -> None:
        pose = self._pose_atual()
        if pose is None:
            return
        _, _, pose_dict = pose
        for combo, chave in (
            (self._combo_braco_d, "braco_dir"),
            (self._combo_braco_e, "braco_esq"),
        ):
            combo.blockSignals(True)
            combo.setCurrentText(str(pose_dict.get(chave, "idle")))
            combo.blockSignals(False)
        self._atualizar_eixos_junta()

    def _atualizar_eixos_junta(self) -> None:
        pose = self._pose_atual()
        if pose is None:
            return
        _, _, pose_dict = pose
        corpo = pose_dict.get("corpo", {})
        junta = self._combo_junta.currentText()
        vec = corpo.get(junta, (0.0, 0.0, 0.0))
        for sp, val in zip(self._spins_xyz, vec, strict=True):
            sp.definir_valor_silencioso(float(val))

    def _on_acento_mudou(self, valor: float) -> None:
        passo = self._passo_atual()
        if passo is None:
            return
        p_idx, _ = passo
        self.campo_editado.emit(
            "Editar acento da frase",
            ("DANCA", "frases", self._chave_frase, "passos", p_idx, "acento_forca"),
            float(valor),
        )

    def _on_braco_mudou(self, chave: str, valor: str) -> None:
        pose = self._pose_atual()
        if pose is None:
            return
        p_idx, pose_idx, _ = pose
        self.campo_editado.emit(
            f"Alterar {chave}",
            ("DANCA", "frases", self._chave_frase, "passos", p_idx, "poses", pose_idx, chave),
            valor,
        )

    def _on_eixo_pose_mudou(self) -> None:
        pose = self._pose_atual()
        if pose is None:
            return
        p_idx, pose_idx, _ = pose
        junta = self._combo_junta.currentText()
        rot = (
            float(self._spins_xyz[0].value()),
            float(self._spins_xyz[1].value()),
            float(self._spins_xyz[2].value()),
        )
        self.campo_editado.emit(
            f"Editar {junta} da frase",
            (
                "DANCA",
                "frases",
                self._chave_frase,
                "passos",
                p_idx,
                "poses",
                pose_idx,
                "corpo",
                junta,
            ),
            rot,
        )
