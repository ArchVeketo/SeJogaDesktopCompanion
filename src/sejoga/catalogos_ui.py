"""Catálogos visuais e rótulos humanos unificados entre menus e configurações.

Módulo puro (sem dependências de Panda3D, Qt ou Win32).
"""

from __future__ import annotations

ESTILOS_DANCA_UI: tuple[tuple[str, str], ...] = (
    ("head_bob", "Head Bob"),
    ("hip_hop", "Hip Hop"),
    ("rock", "Rock"),
    ("breakdance", "Breakdance"),
    ("street_groove", "Street Groove"),
    ("graffiti_dance", "Graffiti Dance"),
    ("cyber_bounce", "Cyber Bounce"),
    ("funk_glide", "Funk Glide"),
    ("cyber_skank", "Cyber Skank"),
    ("walkman_shuffle", "Walkman Shuffle"),
    ("electro_swing", "Electro Swing"),
    ("passinho", "Passinho / Fancy Feet"),
    ("master_of_mystery", "Master of Mystery"),
    ("she_bugging", "She Bugging"),
    ("miku", "Miku"),
    ("dont_start_now", "Don't Start Now"),
    ("popular", "Popular · The Weeknd"),
    ("griddy", "Griddy"),
    ("boogie_down", "Boogie Down"),
    ("jabba_switchway", "Jabba Switchway"),
    ("go_mufasa", "Go Mufasa"),
    ("jazz_dance", "Jazz Dance"),
    ("criss_cross", "Criss Cross"),
    ("celebration_dance", "Celebration Dance"),
    ("kpop_dance_03", "K-Pop Dance"),
    ("macaroons", "Macarena / Macaroons"),
    ("speed_dial", "Speed Dial"),
    ("cyclone_headbang", "Cyclone Headbang"),
    ("january_bop", "January Bop"),
    ("jiggle", "Jiggle Jiggle"),
    ("lets_begin", "Let's Begin"),
    ("aloa", "Aloa"),
    ("bbd", "BBD"),
    ("flair", "Flair Breakdance"),
    ("breakdance_1990", "Breakdance 1990"),
    ("breakdance_freeze", "Breakdance Freeze"),
    ("breakdance_uprock", "Breakdance Uprock"),
    ("dancing_twerk", "Groove Twerk"),
)

ESTILOS_DANCA_RAPIDOS_MASCOTE: tuple[tuple[str, str], ...] = (
    ("funk_glide", "Funk Glide"),
    ("cyber_skank", "Cyber Skank"),
    ("walkman_shuffle", "Walkman Shuffle"),
    ("street_groove", "Street Groove"),
    ("graffiti_dance", "Graffiti Dance"),
    ("cyber_bounce", "Cyber Bounce"),
    ("hip_hop", "Hip Hop"),
    ("rock", "Rock"),
    ("electro_swing", "Electro Swing"),
    ("passinho", "Passinho"),
)

FILTROS_VISUAIS_UI: tuple[tuple[str, str], ...] = (
    ("blockbench", "Blockbench (Padrão · Soft Shading)"),
    ("street", "Street (Pôster Vivo / Persona)"),
    ("anime", "Anime (Manpu & Cel-Shading)"),
    ("spiderverse", "Spider-Verse (12 FPS & HQ Rabiscada)"),
    ("holograma", "Holograma (CRT & Sinal Instável)"),
)

PALETAS_VFX_UI: tuple[tuple[str, str], ...] = (
    ("auto", "Somente os efeitos do filtro"),
    ("pb_escuro", "Sumi-e Mangá (Nanquim & Shūchūsen)"),
    ("pb_claro", "Caderno Vivo (Origami & Sketchbook)"),
    ("colorido", "Street Cyberfunk (Spray, Gotas & Setas)"),
    ("hifi_rush", "Hi-Fi Beat (Anéis 3D, EQ & Faíscas)"),
    ("spider_verse", "Aranhaverso (Glitch CMYK & Sentido-Aranha)"),
    ("anime_sakuga", "Anime Sakuga (Cubos, Aura & Ki)"),
    ("lowpoly_3d", "Retro 3D Low-Poly (Notas, Raios & Cristais)"),
)

ABERTURAS_UI: tuple[tuple[str, str], ...] = (
    ("fade_in", "Fade in (dissolver)"),
    ("virtual_insanity_in", "Virtual Insanity (deslizando)"),
    ("run_from_depth", "Correndo do fundo"),
    ("kagebunshin_in", "Entrada ninja (Kage Bunshin)"),
    ("sandevistan_in", "Sandevistan (lateral)"),
    ("goku_teleport_in", "Teleporte do Goku (Shunkan Idō)"),
    ("hero_drop_in", "Queda Heroica (impacto)"),
)

ABERTURAS_CONFIG_UI: tuple[tuple[str, str], ...] = (
    ("padrao", "Instantânea (padrão)"),
    *ABERTURAS_UI,
    ("aleatoria", "Aleatória ao abrir"),
)

ENCERRAMENTOS_UI: tuple[tuple[str, str], ...] = (
    ("classic", "Clássica (arremesso)"),
    ("sonic_classic", "Sonic Classic (pulo e queda)"),
    ("fnf_blue_balls", "FNF Blue Balls"),
    ("lego_disassemble", "Desmontar LEGO"),
    ("thanos_snap", "Desintegrar (Thanos)"),
    ("peace_fade_out", "Fade out Peace Sign"),
    ("virtual_insanity_out", "Virtual Insanity (deslizando)"),
    ("cyberpsicopata_out", "Cyberpsicopata (glitch)"),
    ("goku_teleport_out", "Teleporte do Goku (Shunkan Idō)"),
    ("portal_pull_out", "Fenda Dimensional (espiral)"),
)

ENCERRAMENTOS_CONFIG_UI: tuple[tuple[str, str], ...] = (
    *ENCERRAMENTOS_UI,
    ("aleatoria", "Aleatória ao encerrar"),
)

PERSONALIDADES_IDLE_UI: tuple[tuple[str, str], ...] = (
    ("auto", "Automático (reage ao humor)"),
    ("brc_malandro", "Malandro de Rua · BRC"),
    ("frenetico_groove", "Groove Vivo · FNF / Hi-Fi"),
    ("espreita_armario", "Segredo Vivo · Armário Suspeito"),
    ("jojo_exibido", "Teatral · JoJo / Persona"),
    ("boxeador_pronto", "Marrento de Arcade · Guarda"),
    ("derretido_sono", "Bateria 1% · Pescando em Pé"),
)

CENAS_IDLE_UI: tuple[tuple[str, str], ...] = (
    ("conferir_estilo", "Conferir o estilo"),
    ("espreguicar_pesado", "Espreguiçar pesado"),
    ("olhar_curioso_chao", "Olhar curioso no chão"),
    ("conferir_luva", "Conferir a luva"),
    ("pensar_gabinete", "Pensar com o gabinete"),
    ("segurar_porta_timido", "Segurar a porta (tímido)"),
    ("checar_walkman", "Checar Walkman no cinto"),
    ("alongar_pescoco_ombros", "Alongar pescoço e ombros"),
    ("groove_um_pe", "Groove em um pé"),
    ("escutar_fone", "Escutar fone"),
    ("batida_guardada", "Batida guardada"),
    ("disfarcar_olhar", "Disfarçar o olhar"),
    ("ajeitar_fone", "Ajeitar o fone"),
    ("fone_com_problema", "Esse fone tá com problema?"),
    ("argolas_antena", "Argolas da antena"),
    ("finger_guns_camera", "Arminha pra câmera (Ayyy!)"),
    ("bater_pe_impaciente", "Bater o pé impaciente"),
    ("bater_pe_ritmo", "Bater o pé no ritmo"),
    ("solo_guitarra_ar", "Solo de guitarra no ar"),
    ("tentaculo_fujao", "Tentáculo fujão (armário vivo)"),
    ("cacar_cursor_sucesso", "Caçar cursor (conseguiu!)"),
    ("cacar_cursor_falha", "Caçar cursor (errou / triste)"),
    ("roubo_cursor_tentaculo", "Roubo do cursor (tentáculo)"),
    ("cuspir_item", "Cuspir item do armário"),
)

ACOES_RAPIDAS_MASCOTE_UI: tuple[tuple[str, str], ...] = (
    ("celebrate", "Comemorar"),
    ("finger_guns_camera", "Arminha pra câmera"),
    ("solo_guitarra_ar", "Solo de guitarra no ar"),
    ("cuspir_item", "Cuspir item do armário"),
    ("cacar_cursor_sucesso", "Caçar o cursor"),
    ("tentaculo_fujao", "Tentáculo fujão"),
    ("conferir_estilo", "Conferir o estilo"),
    ("espreguicar_pesado", "Espreguiçar pesado"),
    ("olhar_curioso_chao", "Olhar curioso no chão"),
    ("wave", "Acenar"),
    ("peek", "Mostrar tentáculos"),
    ("sneeze", "Espirro de tentáculos"),
    ("argolas_antena", "Argolas da antena"),
    ("checar_walkman", "Checar Walkman"),
)
