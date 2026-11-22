# Texto en espanol -> fonemas -> frames para el sintetizador de formantes.
# Compatible con CPython y MicroPython (sin dependencias). Lo usan:
#   - la simulacion (WAVs), el modelo bit-exacto y la pagina web (portado a JS)
#   - el script de la tarjeta Tiny Tapeout (main_voz.py)
#
# Un frame es la tupla (b1, b2, b3, inc, amp, modo, sh) que se escribe en el chip.

import math

FS = 10000000 / 1024      # 9765.625 Hz (reloj de 10 MHz / 1024)
K = 4
PH = 13
FRAME_MS = 5
SAMPLES_PER_FRAME = 49    # ~5 ms en simulacion (la tarjeta usa su propio reloj)

VOZ, RUIDO, MIXTO, SIL = 1, 2, 3, 0

_R = math.sqrt(1.0 - 2.0 ** -K)


def coef(f_hz):
    """B = 2 r cos(2 pi F / fs) en Q2.10 (12 bits con signo)."""
    b = int(round(2.0 * _R * math.cos(2.0 * math.pi * f_hz / FS) * 1024))
    return max(-2048, min(2047, b))


def inc_pitch(f0):
    return max(0, min(1023, int(round(f0 * (1 << PH) / FS))))


# Fonema: (F1, F2, F3, amp, modo, duracion_ms, clase, sh)
#   amp y sh (atenuacion 2^-sh de la fuente) estan calibrados con el modelo
#   bit-exacto para que ningun resonador sature y el volumen sea parejo.
#   clase: 'v' vocal, 'a' aproximante/liquida/nasal, 'f' fricativa,
#          'p' oclusiva sorda (cierre + explosion), 't' vibrante simple
FON = {
    'a':  (750, 1300, 2500, 51, VOZ, 110, 'v', 0),
    'e':  (460, 1850, 2550, 57, VOZ, 100, 'v', 0),
    'i':  (290, 2250, 2950, 83, VOZ, 95, 'v', 1),
    'o':  (500, 900, 2450, 53, VOZ, 105, 'v', 2),
    'u':  (310, 750, 2350, 32, VOZ, 95, 'v', 3),
    'l':  (360, 1250, 2600, 21, VOZ, 60, 'a', 1),
    'm':  (270, 1050, 2300, 14, VOZ, 70, 'a', 2),
    'n':  (270, 1550, 2550, 17, VOZ, 65, 'a', 1),
    'ny': (270, 1900, 2700, 27, VOZ, 80, 'a', 1),
    'b':  (300, 900, 2200, 10, VOZ, 50, 'a', 2),
    'd':  (320, 1500, 2500, 20, VOZ, 45, 'a', 1),
    'g':  (300, 1700, 2300, 19, VOZ, 50, 'a', 1),
    'y':  (280, 2150, 2800, 43, VOZ, 65, 'a', 1),
    'r':  (450, 1450, 2400, 21, VOZ, 25, 't', 0),
    'rr': (450, 1450, 2400, 29, MIXTO, 90, 't', 0),
    's':  (2600, 3300, 3700, 12, RUIDO, 100, 'f', 0),
    'f':  (1400, 2400, 3400, 30, RUIDO, 95, 'f', 0),
    'j':  (1100, 1900, 2700, 24, RUIDO, 95, 'f', 0),
    'ch': (2100, 2800, 3500, 30, RUIDO, 70, 'f', 0),
    'p':  (700, 1100, 2400, 16, RUIDO, 15, 'p', 1),
    't':  (1700, 2700, 3500, 49, RUIDO, 15, 'p', 0),
    'k':  (1300, 1900, 2600, 24, RUIDO, 20, 'p', 0),
    '_':  (500, 1500, 2500, 0, SIL, 120, 's', 0),   # pausa (coma)
    '.':  (500, 1500, 2500, 0, SIL, 250, 's', 0),   # pausa larga
}

# Palabras con lectura especial (siglas, etc.)
DICC = {
    'ieee': 'i triple e',
    'tt': 'ti ti',
    'rp2350': 'erre pe dos mil trescientos cincuenta',
    'ok': 'okei',
    'y': 'i',
}

_ACENTOS = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u'}
_VOC = 'aeiou'
_NUM = ['cero', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve']


def _palabra_a_fonemas(w):
    """Devuelve lista de (fonema, tonica)."""
    if w in DICC:
        out = []
        for p in DICC[w].split():
            out += _palabra_a_fonemas(p)
        return out
    # posicion de la vocal tonica
    acento = -1
    plano = ''
    for i, c in enumerate(w):
        if c in 'áéíóú':
            acento = i
        plano += _ACENTOS.get(c, c)
    w = plano
    res = []
    i = 0
    n = len(w)
    while i < n:
        c = w[i]
        nx = w[i + 1] if i + 1 < n else ''
        if c == 'h':
            i += 1
            continue
        if c == 'c' and nx == 'h':
            res.append(('ch', i)); i += 2; continue
        if c == 'l' and nx == 'l':
            res.append(('y', i)); i += 2; continue
        if c == 'r' and nx == 'r':
            res.append(('rr', i)); i += 2; continue
        if c == 'r':
            res.append(('rr' if i == 0 else 'r', i)); i += 1; continue
        if c == 'q':
            res.append(('k', i)); i += 2 if nx == 'u' else 1; continue
        if c == 'g' and nx == 'u' and i + 2 < n and w[i + 2] in 'ei':
            res.append(('g', i)); i += 2; continue
        if c == 'g' and nx in ('e', 'i'):
            res.append(('j', i)); i += 1; continue
        if c == 'c':
            res.append(('s' if nx in ('e', 'i') else 'k', i)); i += 1; continue
        if c == 'z':
            res.append(('s', i)); i += 1; continue
        if c == 'v':
            res.append(('b', i)); i += 1; continue
        if c == 'ñ':
            res.append(('ny', i)); i += 1; continue
        if c == 'x':
            res.append(('k', i)); res.append(('s', i)); i += 1; continue
        if c == 'w':
            res.append(('u', i)); i += 1; continue
        if c == 'y':
            res.append(('i' if (nx == '' or nx not in _VOC) else 'y', i)); i += 1; continue
        if c in FON:
            res.append((c, i))
        i += 1
    # silabas: vocales seguidas forman diptongo salvo dos fuertes o debil con tilde
    grupos = []
    for k, (f, pos) in enumerate(res):
        if FON[f][6] != 'v':
            continue
        fuerte = f in 'aeo' or pos == acento
        if grupos and grupos[-1][-1] == k - 1:
            ant = res[k - 1][0]
            ant_fuerte = ant in 'aeo' or res[k - 1][1] == acento
            if not (fuerte and ant_fuerte):
                grupos[-1].append(k)
                continue
        grupos.append([k])
    ton = -1
    if acento >= 0:
        for k, (f, pos) in enumerate(res):
            if pos == acento:
                ton = k
    elif grupos:
        ult = w[-1] if w else ''
        if (ult in _VOC or ult in 'ns') and len(grupos) >= 2:
            g = grupos[-2]
        else:
            g = grupos[-1]
        ton = g[-1]
        for k in g:
            if res[k][0] in 'aeo':
                ton = k
    return [(f, k == ton) for k, (f, _) in enumerate(res)]


_MAYUS = {'Á': 'á', 'É': 'é', 'Í': 'í', 'Ó': 'ó', 'Ú': 'ú', 'Ü': 'ü', 'Ñ': 'ñ'}


def texto_a_fonemas(texto):
    t = ''.join(_MAYUS.get(c, c) for c in texto).lower()
    out = []
    pal = ''
    for c in t + ' ':
        if c.isalpha() or c in 'áéíóúüñ' or c.isdigit():
            pal += c
            continue
        if pal:
            if pal.isdigit():
                for d in pal:
                    out += _palabra_a_fonemas(_NUM[int(d)])
            else:
                out += _palabra_a_fonemas(pal)
            pal = ''
        if c in ',;:':
            out.append(('_', False))
        elif c in '.!?':
            out.append(('.', False))
    while out and out[-1][0] in '_.':
        out.pop()
    return out


def _lerp(a, b, t):
    return a + (b - a) * t


def fonemas_a_frames(fonemas, f0_ini=135.0, f0_fin=100.0, tasa=1.0):
    """Genera frames de 5 ms con transiciones suaves de formantes."""
    # duraciones en frames
    durs = []
    for f, ton in fonemas:
        d = FON[f][5] * (1.3 if ton else 1.0) / tasa
        durs.append(max(1, int(round(d / FRAME_MS))))
    total = sum(durs) or 1
    frames = []
    prev = None          # (F1, F2, F3) del fonema anterior
    prev_sh = 0
    pos = 0
    for idx, (f, ton) in enumerate(fonemas):
        F1, F2, F3, amp, modo, _, clase, sh = FON[f]
        nf = durs[idx]
        tgt = (F1, F2, F3)
        if clase in ('p', 's') or prev is None:
            ini = tgt
        else:
            ini = prev
        trans = min(nf, 6)  # 30 ms de transicion
        for k in range(nf):
            t = 1.0 if trans <= 1 else min(1.0, k / (trans - 1.0))
            F = [_lerp(ini[q], tgt[q], t) for q in range(3)]
            f0 = _lerp(f0_ini, f0_fin, (pos + k) / total) + (18.0 if ton else 0.0)
            a = amp
            m = modo
            shf = max(sh, prev_sh) if k < trans else sh
            if clase == 'p':
                # cierre (silencio) y luego explosion de ruido
                cierre = max(1, nf * 3)
                frames += [(coef(F1), coef(F2), coef(F3), inc_pitch(f0), 0, SIL, sh)] * cierre
                nf_burst = nf
                for q in range(nf_burst):
                    frames.append((coef(F1), coef(F2), coef(F3), inc_pitch(f0),
                                   int(amp * (1.0 - q / (nf_burst + 1.0))), RUIDO, sh))
                break
            if clase == 't':
                # vibrante: hueco breve de amplitud a mitad del sonido
                a = amp if (k % 4) < 2 else amp // 3
            if clase == 'v':
                # rampa de entrada / salida de 10 ms
                if k == 0 and (idx == 0 or FON[fonemas[idx - 1][0]][6] in ('s', 'p', 'f')):
                    a = amp // 2
                if k == nf - 1 and (idx == len(fonemas) - 1 or FON[fonemas[idx + 1][0]][6] in ('s',)):
                    a = amp // 2
            a = min(255, int(a) << (shf - sh))   # compensa la atenuacion extra
            frames.append((coef(F[0]), coef(F[1]), coef(F[2]), inc_pitch(f0), a, m, shf))
        prev = tgt
        prev_sh = sh
        pos += nf
    # cola de silencio
    frames += [(coef(500), coef(1500), coef(2500), inc_pitch(100), 0, SIL, 0)] * 8
    return frames


def texto_a_frames(texto, **kw):
    return fonemas_a_frames(texto_a_fonemas(texto), **kw)


def vocal_frames(v, ms=500, f0=120.0):
    F1, F2, F3, amp, _, _, _, sh = FON[v]
    n = ms // FRAME_MS
    fr = []
    for k in range(n):
        a = amp if 4 <= k < n - 4 else amp // 2
        fr.append((coef(F1), coef(F2), coef(F3), inc_pitch(f0), a, VOZ, sh))
    return fr
