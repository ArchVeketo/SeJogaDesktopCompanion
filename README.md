<div align="center">

# 🎮 SeJoga Desktop Companion

**Mascote 3D interativo para Windows** — Mário vive no seu desktop!

![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat&logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=flat&logo=python&logoColor=white)
![Panda3D](https://img.shields.io/badge/Panda3D-Game%20Engine-orange?style=flat)
![License](https://img.shields.io/badge/license-MIT-green?style=flat)

[Recursos](#-recursos) • [Instalação](#-instalação) • [Como Usar](#-como-usar) • [Desenvolvimento](#-desenvolvimento) • [Documentação](#-documentação)

</div>

---

## ✨ Recursos

### 🎭 **Animações Procedurais**
- **9 personalidades diferentes** (Tranquila, Curiosa, Brincalhona, Tímida, Confiante, Street, Fighter, Rhythm, Stylish)
- Animações reativas ao cursor, cliques e música
- Movimento fluido com física de inércia corporal
- Pernas e tentáculos articulados

### 🖱️ **Interação Intuitiva**
- **Arrastar e soltar** com física realista
- **Hover** para chamar atenção
- **Cliques** para interações (esquerdo: reação, direito: carinho, meio: cutucada)
- Overlay transparente que não bloqueia cliques

### 🎨 **Customização Visual**
- Contorno configurável (cor, espessura 0.5-8px, on/off)
- Escala ajustável (0.5x-2.5x)
- Múltiplas posições Z (sempre no topo, normal, atrás das janelas)

### 🎵 **Reação à Música**
- Dança sincronizada com batidas
- Suporte a Windows Media Session
- Suporte a loopback de áudio do sistema

### 🪼 **Tentáculos 3D**
- Física procedural com 8 segmentos cada
- Emergem da porta do personagem
- Gotejam gosma rosa ocasionalmente

---

## 📦 Instalação

### Build no Ambiente Atual

```powershell
# Clone o repositório
git clone https://github.com/ArchVeketo/SeJogaDesktopCompanion.git
cd SeJogaDesktopCompanion

# Instale as dependências
pip install -e .

# Execute o companion
sejoga

# Ou faça o build do executável
.\build.ps1
```

O executável gerado fica em `dist\SeJogaCompanion\SeJogaCompanion.exe`.

> **Nota**: O script de build usa Python 3.14. A portabilidade para outras versões e validação em máquinas limpas ainda está em andamento.

---

## 🎮 Como Usar

### Interações Básicas

#### 🖱️ Mouse
- **Hover**: Passe o cursor sobre Mário — ele olha para você e entreabre a porta
- **Clique Esquerdo**: Reação rápida de surpresa
- **Clique Direito**: Carinho — ele adora!
- **Botão do Meio**: Cutucada — cuidado, ele não gosta muito
- **Arrastar**: Segure o botão esquerdo e mova pelo menos 6 pixels
  - Solte para posicionar (posição é salva automaticamente)
  - `Esc` interrompe o arraste e mantém na posição atual

#### ⚙️ Configurações
Acesse com `Ctrl + Alt + S` ou pelo menu da bandeja:

- **Personalidade do Idle**: Escolha entre 9 estilos diferentes ou deixe automático
- **Física**: Ative para permitir arremeços, quedas e colisões
- **Reação à Música**: Windows Media Session ou loopback de áudio
- **Contorno**: Cor, espessura, on/off
- **Atalhos**: Customize todos os atalhos globais

#### 🎪 Gestos Especiais
No menu da bandeja:
- **Acenar**: Mário acena para você energeticamente
- **Soltar os ombros**: Gesto de ajustar a jaqueta
- **Mostrar tentáculos**: Os tentáculos emergem da porta

### Física e Arremeço

Com a física ativada:
- **Soltar em movimento**: Arremessa Mário com física realista
- **Queda**: Ele cai, quica e repousa no chão ou no topo de janelas
- **Colisão circular**: Detecta bordas do monitor e janelas
- **Soltar parado**: Elimina o impulso, apenas posiciona

> **Dica**: Use `Esc` durante o arraste para cancelar sem arremessar!

---

## 🛠️ Desenvolvimento

### Estrutura do Projeto

```
SeJogaDesktopCompanion/
├── src/sejoga/           # Código principal
│   ├── animation.py      # Controlador de animações
│   ├── rig.py           # Sistema de rig procedural
│   ├── physics.py       # Física de tela
│   ├── tentacle_system.py # Sistema de tentáculos
│   └── window.py        # Overlay e renderização
├── assets/              # Modelos 3D, texturas, ícones
├── docs/                # Documentação técnica
└── tests/               # Testes automatizados
```

### Tecnologias

- **[Panda3D](https://www.panda3d.org/)**: Engine de renderização 3D
- **[PySide6](https://doc.qt.io/qtforpython/)**: Interface Qt (bandeja, configurações)
- **[Pydantic](https://docs.pydantic.dev/)**: Validação de configurações
- **[Pytest](https://docs.pytest.org/)**: Framework de testes

### Executar Testes

```powershell
pytest tests/ -v
```

### Build para Produção

```powershell
.\build.ps1
```

Gera executável standalone em `dist\SeJogaCompanion\`.

---

## 📚 Documentação

### Documentos Principais
- [**Status e Próximos Passos**](docs/STATUS_E_PROXIMOS_PASSOS.md) — Roadmap e features implementadas
- [**Arquitetura**](docs/ARQUITETURA.md) — Visão técnica do sistema
- [**Guia de Animações**](docs/GUIA_ANIMACOES_COMPANION.md) — Como criar animações
- [**Referência de Animações**](docs/REFERENCIA_ANIMACOES.md) — API completa do sistema de animação
- [**Pesquisa Técnica**](docs/PESQUISA.md) — Decisões técnicas e alternativas exploradas
- [**Melhorias de Animação 2026-11-04**](docs/MELHORIAS_ANIMACAO_2026-11-04.md) — Últimas melhorias

### Para Desenvolvedores
Consulte também os skills no diretório `.agents/skills/` para workflows específicos:
- `sejoga-blockbench-animation`: Workflow para animações no Blockbench
- `sejoga-release-build`: Processo de build de release
- `sejoga-win32-overlay-debug`: Debug de overlay Win32

---

## 🎯 Roadmap

### ✅ Implementado
- [x] Overlay transparente com click-through
- [x] Sistema de rig procedural com 9 personalidades
- [x] Física de tela com colisões
- [x] Sistema de tentáculos 3D articulados
- [x] Reação à música (Media Session + loopback)
- [x] Customização completa via UI
- [x] Atalhos globais configuráveis
- [x] Build PyInstaller onedir

### 🚧 Em Andamento
- [ ] Validação em instalação limpa do Windows
- [ ] Suporte multi-monitor aprimorado
- [ ] Sistema de plugins

### 🔮 Planejado
- [ ] Mais personalidades e gestos
- [ ] Sistema de conquistas/achievements
- [ ] Minigames interativos
- [ ] Integração com Discord Rich Presence

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:
1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

---

## 📝 Licença

Este projeto é distribuído sob a licença MIT. Veja `LICENSE` para mais informações.

---

## 🎨 Créditos

Baseado no universo **SeJoga** — arte e conceito originais.

Desenvolvido com ❤️ usando:
- Panda3D para renderização 3D
- PySide6 para interface
- Muito café ☕

---

<div align="center">

**[⬆ Voltar ao topo](#-sejoga-desktop-companion)**

Feito com 🎮 por [ArchVeketo](https://github.com/ArchVeketo)

</div>
