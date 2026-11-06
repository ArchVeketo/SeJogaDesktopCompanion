# Validação manual do updater (máquina com GPU — 11/nov)

O ambiente de desenvolvimento atual cai para `p3tinydisplay` (sem GPU) e não
permite testar o UAC/elevação real nem o ciclo visual completo da atualização.
O que foi verificado aqui por automação:

- `SeJogaLauncher.cs` compila via `tools\build-launcher.ps1` (csc .NET Framework).
- VERSION_INFO do `.exe` preenchido (produto "Se Joga Desktop Companion",
  empresa "Se Joga no Armário"), confirmado por `FileVersionInfo`.
- Lógica Python do fluxo fecha->barra->reabre coberta por `tests/test_update_ui.py`
  (handoff ao launcher dispara o fechamento do companion nos dois caminhos de UI)
  e pelo `tools/smoke-updater.py` (loopback, sem rede real).

## Checklist a validar na máquina com GPU

Pré-requisito: instalar via instalador oficial (runtime em `runtime\current`,
`SeJogaLauncher.exe` e `channel-info.json` na raiz da instalação em Program Files).

1. [ ] Abrir o Mário normalmente: fundo transparente, sem bloco preto.
2. [ ] Bandeja → "Buscar atualizações..." → confirmar que detecta a versão do
       canal e mostra "Atualizar agora".
3. [ ] Confirmar a atualização: o Mário **fecha imediatamente** (não fica
       renderizando atrás) e aparece **só a barra de progresso**.
4. [ ] UAC aparece mostrando o editor **"Se Joga no Armário"** (o aviso de
       editor não verificado continua, pois não há assinatura de código).
5. [ ] Barra mostra progresso real do download: porcentagem + "X.X MB de Y.Y MB".
6. [ ] Estados textuais aparecem em sequência: "Baixando…", "Verificando…",
       "Instalando: extraindo…", "Aplicando a atualização…", "Atualização concluída.".
7. [ ] Ao terminar, o Mário **reabre automaticamente** na nova versão.
8. [ ] Repetir o passo 3 e **cancelar o UAC**: a barra fecha e o Mário **reabre**
       (não pode ficar fechado).
9. [ ] Repetir o fluxo pela janela de Configurações (seletor de canal + "Buscar
       atualizações"): mesmo comportamento fecha->barra->reabre.
10. [ ] Conferir que as configurações do usuário foram preservadas após atualizar.

## Gancho futuro: assinatura de código

Não há certificado por ora (decisão do usuário: deixar o aviso do Windows como
está). O passo de `signtool` está **comentado e documentado** em
`tools\build-launcher.ps1`. Quando houver um `.pfx`, descomentar e preencher as
variáveis de ambiente `SEJOGA_CERT_PFX` / `SEJOGA_CERT_SENHA` para assinar o
`SeJogaLauncher.exe` e remover o aviso de editor desconhecido do UAC.
