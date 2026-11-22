# Demo para la tarjeta Tiny Tapeout (RP2350 + MicroPython SDK "ttboard").
#
# Copia a la tarjeta:  voz_es.py  y  main_voz.py
#   >>> import main_voz
#   >>> main_voz.decir("Hola, IEEE")
#   >>> main_voz.vocales()
#   >>> main_voz.conversar()        # escribe frases y el chip las dice
#
# Audio: uo[0] (AUDIO_PDM) -> RC pasabajas (1 kOhm + 47 nF) -> amplificador -> bocina.

import time
import voz_es

PROYECTO = 'tt_um_glimmerquark_voz'
CLK_HZ = 10_000_000
FRAME_US = voz_es.FRAME_MS * 1000

_tt = None


def iniciar(tt=None):
    global _tt
    if tt is None:
        from ttboard.demoboard import DemoBoard
        tt = DemoBoard.get()
    from ttboard.mode import RPMode
    tt.mode = RPMode.ASIC_RP_CONTROL
    proyecto = getattr(tt.shuttle, PROYECTO, None)
    if proyecto is None:
        encontrados = tt.shuttle.find('voz')
        if not encontrados:
            raise RuntimeError('No encontre %s en este shuttle' % PROYECTO)
        proyecto = encontrados[0]
    proyecto.enable()
    tt.uio_oe_pico.value = 0xFF          # el RP maneja los 8 uio (dato, direccion, strobe)
    tt.uio_in.value = 0
    tt.ui_in.value = 0
    tt.clock_project_PWM(CLK_HZ)
    tt.reset_project(True)
    time.sleep_ms(1)
    tt.reset_project(False)
    time.sleep_ms(1)
    _tt = tt
    return tt


def escribir(addr, valor):
    """Escribe un registro de 12 bits (el chip sincroniza el strobe)."""
    tt = _tt
    hi = ((addr & 7) << 4) | ((valor >> 8) & 0xF)
    tt.ui_in.value = valor & 0xFF
    tt.uio_in.value = hi | 0x80          # strobe alto (dura >> 3 ciclos de 100 ns)
    tt.uio_in.value = hi                 # strobe bajo


def escribir_frame(fr):
    b1, b2, b3, inc, amp, modo, sh = fr
    escribir(0, b1 & 0xFFF)
    escribir(1, b2 & 0xFFF)
    escribir(2, b3 & 0xFFF)
    escribir(3, inc & 0x3FF)
    escribir(4, ((sh & 3) << 10) | ((modo & 3) << 8) | (amp & 0xFF))


def silencio():
    escribir(4, 0)


def tocar(frames):
    if _tt is None:
        iniciar()
    t = time.ticks_us()
    for fr in frames:
        escribir_frame(fr)
        t = time.ticks_add(t, FRAME_US)
        while time.ticks_diff(t, time.ticks_us()) > 0:
            pass
    silencio()


def decir(texto, tono=1.0, tasa=1.0):
    """Dice un texto en espanol. tono escala F0, tasa la velocidad."""
    fon = voz_es.texto_a_fonemas(texto)
    print(' '.join(f + ("'" if t else '') for f, t in fon))
    frames = voz_es.fonemas_a_frames(fon, f0_ini=135.0 * tono, f0_fin=100.0 * tono, tasa=tasa)
    tocar(frames)


def vocales():
    for v in 'aeiou':
        tocar(voz_es.vocal_frames(v, ms=500))
        time.sleep_ms(150)


def conversar():
    print('Escribe una frase (vacio para salir)')
    while True:
        s = input('> ')
        if not s:
            break
        decir(s)
