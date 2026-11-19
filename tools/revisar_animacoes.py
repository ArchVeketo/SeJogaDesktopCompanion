"""Revisão visual do catálogo na janela real, com perfil isolado e pranchas sequenciais."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--grupo', choices=('idle','danca','acoes','extras','movimento','sono','todos'), default='todos')
    args = parser.parse_args()
    import PySide6.QtWidgets  # noqa: F401 — Qt precisa carregar antes do Panda.
    from PIL import Image, ImageDraw
    from panda3d.core import ClockObject, Point2
    from sejoga.configuracao import Settings
    from sejoga.render.janela import OverlayApp
    from sejoga.animacao.animation import IDLE_CLIPS, CENAS_IDLE
    from sejoga.animacao.danca_clipes import listar_clipes_emote
    from sejoga.animacao.animacao_entrada import IntroAnimation
    from sejoga.animacao.animacao_saida import ExitAnimation

    out = Path(tempfile.mkdtemp(prefix='sejoga-catalogo-'))
    os.environ['SEJOGA_CONFIG_PATH'] = str(out/'config.toml')
    settings = Settings()
    settings.physics.enabled = settings.music.enabled = False
    settings.window.start_position = (650,480)
    app = OverlayApp(settings)
    app.hotkey_manager.close()
    app.taskMgr.remove('mouse-poll')
    r, ctrl = app.renderer, app.animation_controller
    clock = ClockObject.getGlobalClock()
    clock.setMode(ClockObject.MNonRealTime)
    clock.setDt(1/30)
    ctrl.agendador_pacotes.tempo_ate_proximo_s = 1e9
    original_update = ctrl.update
    inputs = {}
    def update(dt, **kwargs):
        kwargs.update(hovered=False, look_direction=0, look_vertical=0, pointer_position=None,
                      sleep_after_idle_seconds=0, music_playing=False)
        kwargs.update(inputs)
        return original_update(1/30, **kwargs)
    ctrl.update = update
    def step():
        app._animation_last_tick = time.perf_counter()-1/30
        app.taskMgr.step()
    def capture():
        im=app.win.getScreenshot()
        pt=Point2()
        app.cam.node().getLens().project(r._rig_nodes['body'].getPos(app.cam),pt)
        x=int((1+pt.x)*im.getXSize()/2);y=int((1-pt.y)*im.getYSize()/2)
        img=Image.frombytes('RGB',(im.getXSize(),im.getYSize()),bytes(im.getRamImageAs('RGB'))).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        return img.crop((x-210,y-300,x+210,y+200)).resize((210,250))
    records=[]
    try:
        for _ in range(100):step()
        catalog=[]
        if args.grupo in ('idle','todos'):
            catalog += [('idle',name,float(cfg['duration'])) for name,cfg in IDLE_CLIPS.items()]
            catalog += [('cena',name,float(cfg['duration'])+1) for name,cfg in CENAS_IDLE.items()]
        if args.grupo in ('danca','todos'):
            catalog += [('danca',name,6.) for name in dict.fromkeys(('head_bob','hip_hop','rock','breakdance','street_groove','graffiti_dance','cyber_bounce',*listar_clipes_emote()))]
        if args.grupo in ('acoes','todos'):
            catalog += [('acao',state.value,float(duration)+1) for state,duration in ctrl.REACTION_SECONDS.items()]
        if args.grupo in ('acoes','sono','todos'):
            catalog += [('sono',name,5.) for name in ('em_pe','sentado','deitado')]
        if args.grupo in ('acoes','movimento','todos'):
            catalog += [('movimento',name,4.) for name in ('walk','run','drag','fall')]
        if args.grupo in ('extras','todos'):
            catalog += [('entrada',n,d+1) for n,d in IntroAnimation.DURATIONS.items() if n!='padrao']
            catalog += [('saida',n,d+1) for n,d in ExitAnimation.STYLE_DURATIONS.items()]
            catalog += [('conexao','hip_hop-rock',5.), ('porta','peek',14.)]
        print(out,flush=True)
        for kind,name,duration in catalog:
            inputs.clear()
            ctrl.voltar_ao_plano()
            ctrl._dance_preview_remaining=0
            ctrl._reaction=None
            ctrl._sleep_locked=False
            ctrl._cena_idle_nome=''
            ctrl.appendage_remaining=0
            ctrl._cooldowns.clear()
            r.tentacle_director.encerrar_espiada(interromper=True)
            for _ in range(45):step()
            if kind=='idle':ctrl.set_idle_personality(name)
            elif kind=='cena':ctrl.interact(name)
            elif kind=='danca':ctrl.preview_dance(name)
            elif kind in ('acao','porta'):ctrl.interact(name)
            elif kind=='entrada':app.start_intro(name)
            elif kind=='saida':app.preview_exit(name)
            elif kind=='conexao':ctrl.preview_dance('hip_hop')
            elif kind=='sono':ctrl.colocar_para_dormir(name)
            elif kind=='movimento':
                inputs.update(velocity=(140.,0.) if name=='walk' else (800.,0.) if name=='run' else (0.,250.),grounded=name not in ('drag','fall'),gravity_active=name=='fall',dragging=name=='drag')
            frames=[]; movie=[]; states=set()
            total=round(duration*30)
            sample_at={0,5,12,round(total*.35),round(total*.65),total-1}
            for i in range(total):
                if kind=='entrada' and app._intro_started is not None:
                    app._intro_started=time.perf_counter()-i/30
                if kind=='saida' and app._exit_started is not None:
                    app._exit_started=time.perf_counter()-i/30
                    app._exit_last_tick=time.perf_counter()-1/30
                if kind=='conexao' and i==total//2:ctrl.preview_dance('rock')
                step();states.add(ctrl.state.value)
                if i in sample_at:frames.append(capture())
                if kind in ("conexao", "porta") and i%3==0:movie.append(capture())
            ctrl._dance_preview_remaining=0;ctrl._reaction=None;inputs.clear()
            if kind=='sono':ctrl.acordar()
            for i in range(45):step()
            frames.append(capture())
            sheet=Image.new('RGB',(210*len(frames),280),'#202029')
            for i,im in enumerate(frames):sheet.paste(im,(210*i,30))
            ImageDraw.Draw(sheet).text((8,8),f'{kind} / {name} / {duration:.1f}s + retorno',fill='white')
            path=out/f'{kind}-{name}.png';sheet.save(path)
            if movie:
                movie[0].save(out/f'{kind}-{name}.gif',save_all=True,append_images=movie[1:],duration=100,loop=0)
            records.append(dict(tipo=kind,nome=name,duracao=duration,estados=sorted(states),prancha=str(path)))
            print(kind,name,sorted(states),flush=True)
        (out/'manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:
        app.debug_tools.close();app.music_listener.stop();app.tray_icon.hide();app.destroy()


if __name__=='__main__':main()
