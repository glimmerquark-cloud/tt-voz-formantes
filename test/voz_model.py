"""Modelo bit-exacto del sintetizador de voz por formantes (tt_um_glimmerquark_voz).

Reproduce, muestra por muestra, lo que calcula src/project.v:

  fuente  -> resonador F1 -> resonador F2 -> resonador F3 -> x amplitud -> out8

Cada resonador:   y[n] = B*y[n-1] - r^2*y[n-2] + x[n]
con r^2 = 1 - 2^-K  (ancho de banda fijo ~97 Hz a 9.77 kHz) y B = 2 r cos(2 pi F / fs)
en Q2.10 (12 bits con signo). B*y se calcula con un multiplicador serial LSB-first
de 12 pasos que trunca en cada paso; el resultado es exactamente floor(B*4y / 4096).
"""

W = 14          # bits de los estados de los resonadores
PH = 13         # bits del acumulador de fase (pitch)
S = 8           # bits de la fuente (diente de sierra / ruido)
K = 4           # r^2 = 1 - 2^-K
CYCLES = 1024   # ciclos de reloj por muestra (10 MHz / 1024 = 9765.625 Hz)
FS = 10_000_000 / 1024
LFSR_SLOT = 14   # ranura en la que el chip lee el LFSR (avanza 1 paso por ciclo)
LFSR_BITS = 15

ACC_W = W + 3

# Direcciones de registro (uio_in[6:4])
REG_B1, REG_B2, REG_B3, REG_INC, REG_AMP = 0, 1, 2, 3, 4

# Registro AMP: [7:0] amplitud, [9:8] modo de fuente, [11:10] atenuacion de la fuente
MODE_SILENCIO, MODE_VOZ, MODE_RUIDO, MODE_MIXTO = 0, 1, 2, 3


def sext(v, bits):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


def sat(v, bits):
    hi = (1 << (bits - 1)) - 1
    lo = -(1 << (bits - 1))
    return hi if v > hi else lo if v < lo else v


def mul12(coef12, yop):
    """Multiplicador serial: 12 pasos LSB-first, el bit 11 pesa negativo."""
    acc = 0
    for i in range(12):
        t = acc
        if (coef12 >> i) & 1:
            t = acc - yop if i == 11 else acc + yop
        acc = t >> 1          # desplazamiento aritmetico (floor)
    return acc


def lfsr_step(s):
    # x^15 + x^14 + 1, desplazando a la izquierda
    fb = ((s >> 14) ^ (s >> 13)) & 1
    return ((s << 1) | fb) & 0x7FFF


def _lfsr_jump_table(n):
    """Columnas de la matriz (GF(2)) que avanza el LFSR n pasos."""
    cols = []
    for b in range(LFSR_BITS):
        v = 1 << b
        for _ in range(n):
            v = lfsr_step(v)
        cols.append(v)
    return cols


def lfsr_jump(s, cols):
    r = 0
    b = 0
    while s:
        if s & 1:
            r ^= cols[b]
        s >>= 1
        b += 1
    return r


_JUMP_SAMPLE = _lfsr_jump_table(CYCLES)
_JUMP_SLOT = _lfsr_jump_table(LFSR_SLOT)


class VozModel:
    def __init__(self):
        self.reset()

    def reset(self):
        self.regs = [0] * 8
        self.y1 = [0, 0, 0]
        self.y2 = [0, 0, 0]
        self.phase = 0
        self.lfsr = lfsr_jump(1, _JUMP_SLOT)   # valor en la ranura 14 de la muestra 0
        self.out8 = 0

    def write(self, addr, value12):
        addr &= 7
        if addr == REG_B3:
            # B3 se guarda con 7 bits: B3 = {d[11:5], 10000}; resolucion
            # ~25 Hz, suficiente para el tercer formante.
            self.regs[addr] = (value12 & 0xFE0) | 0x010
        elif addr <= 4:
            self.regs[addr] = value12 & 0xFFF

    def source(self):
        mode = (self.regs[REG_AMP] >> 8) & 3
        top = self.phase >> (PH - S)                      # S bits sin signo
        saw = top - (1 << (S - 1))                        # diente de sierra con signo
        noise = sext(self.lfsr, S)
        if mode == MODE_SILENCIO:
            return 0
        if mode == MODE_VOZ:
            return saw
        if mode == MODE_RUIDO:
            return noise
        return saw ^ (noise >> 2)                         # mixto: voz + ruido suave

    def source_scaled(self):
        sh = (self.regs[REG_AMP] >> 10) & 3
        return self.source() >> sh                        # atenuacion 2^-sh

    def step(self):
        """Calcula una muestra y devuelve out8 (con signo, -128..127)."""
        x = self.source_scaled()
        for j in range(3):
            b = self.regs[REG_B1 + j]
            y1, y2 = self.y1[j], self.y2[j]
            a = mul12(b, y1 << 2)
            a = a - y2
            a = a + (y2 >> K)
            a = a + x
            yn = sat(sext(a, ACC_W), W)
            self.y2[j] = y1
            self.y1[j] = yn
            x = yn
        amp = self.regs[REG_AMP] & 0xFF
        self.out8 = sat(sext(mul12(amp, x << 2), ACC_W), 8)
        inc = self.regs[REG_INC] & 0x3FF
        self.phase = (self.phase + inc) & ((1 << PH) - 1)
        self.lfsr = lfsr_jump(self.lfsr, _JUMP_SAMPLE)
        return self.out8


def frame_regs(frame):
    """frame = (b1, b2, b3, inc, amp, mode, sh) -> lista de (addr, valor12)."""
    b1, b2, b3, inc, amp, mode, sh = frame
    return [(REG_B1, b1 & 0xFFF), (REG_B2, b2 & 0xFFF), (REG_B3, b3 & 0xFFF),
            (REG_INC, inc & 0x3FF), (REG_AMP, ((sh & 3) << 10) | ((mode & 3) << 8) | (amp & 0xFF))]


def render(frames, samples_per_frame, warmup=0):
    """warmup: muestras calculadas con registros en cero antes del primer frame
    (el chip calcula la muestra 0 justo al salir del reset)."""
    m = VozModel()
    for _ in range(warmup):
        m.step()
    out = []
    for fr in frames:
        for a, v in frame_regs(fr):
            m.write(a, v)
        for _ in range(samples_per_frame):
            out.append(m.step())
    return out
