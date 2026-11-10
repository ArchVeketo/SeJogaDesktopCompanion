# Pipeline de CI/CD (GitHub Actions)

Automatiza o que antes era manual (`build.ps1` -> `tools/construir_atualizacao.py` -> `gh release`).
O pipeline **orquestra os scripts existentes**; não reimplementa a lógica de build/empacote.

## Arquivos

- `ci.yml` — orquestrador: decide **canal** e se **publica**, conforme o gatilho.
- `_build-comum.yml` — workflow reutilizável (`workflow_call`) com o build comum de um canal:
  checkout → setup Python 3.12 → instala o stack → `pytest` (gate) → `ruff check` (gate) →
  `build.ps1` → `tools/construir_atualizacao.py` → (opcional) Inno Setup + `tools/build-installer.ps1` →
  sobe artefatos do Actions e, se `publicar=true`, publica nas Releases.

## Como disparar cada caso

| Caso | Como | Canal | Publica? |
|---|---|---|---|
| Nightly | `git push` na `main` | nightly | sim (automático) |
| Pré-release | criar tag `v*rc*`, ex.: `git tag v0.2.0rc1 && git push origin v0.2.0rc1` | prerelease | sim |
| Release | criar tag `v*` estável, ex.: `git tag v0.2.0 && git push origin v0.2.0` | release | sim |
| Manual | aba **Actions** → **CI/CD** → **Run workflow** | escolhe `canal` | `publicar` **default FALSE** |

O disparo manual (`workflow_dispatch`) aceita `canal` (nightly/prerelease/release),
`gerar_instalador` (bool, default true) e `publicar` (bool, default **false**). Com
`publicar=false` ele apenas builda/empacota e sobe os artefatos do Actions para inspeção,
sem tocar nas Releases.

## Publicação e canais

- O **feed** de cada canal é a Release de tag fixa `updates-<canal>` (`updates-nightly`,
  `updates-prerelease`, `updates-release`), cujos assets são o ZIP + `channel.json` + `.sha256`.
  O updater do app lê `releases/download/updates-<canal>/channel.json`.
- A **release de versão** (tag `v*`) recebe o instalador `.exe` + `.sha256`. Tags `rc` entram
  como pré-release; tags estáveis entram como release.
- `tools/construir_atualizacao.py` e o updater já **rejeitam downgrade / build_id regressivo**.

## Credenciais

Usa o `GITHUB_TOKEN` padrão do Actions (`permissions: contents: write`). **Não precisa de
secret extra.** Assinatura de código (Authenticode) está **fora de escopo** por decisão do
usuário; o `version_info` do executável já vem preenchido pelo launcher nativo.

## Limite conhecido

O runner do GitHub **não tem GPU**. O CI garante **build + empacote + publica**, não a
**aparência** (app abre / overlay / render). A validação visual continua **manual** fora do CI.
