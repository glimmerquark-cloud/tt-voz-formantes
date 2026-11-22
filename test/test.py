# SPDX-License-Identifier: Apache-2.0
"""Pruebas cocotb: el chip contra el modelo bit-exacto, muestra por muestra."""
import os
import random
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, Timer
from cocotb.utils import get_sim_time

import voz_model as vm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demo"))
import voz_es as ve  # noqa: E402

GL = os.environ.get("GATES", "no") == "yes" or os.environ.get("GL_TEST")
CYC = vm.CYCLES
T_NS = 100


def make_clock(dut):
    try:
        return Clock(dut.clk, T_NS, unit="ns")
    except TypeError:
        return Clock(dut.clk, T_NS, units="ns")


class Harness:
    """El flanco de subida m (contando desde 0 tras soltar el reset) ejecuta
    la ranura cnt = m mod 1024 del chip.  Las acciones se hacen en flancos de
    bajada, a medio ciclo."""

    def __init__(self, dut):
        self.dut = dut
        self.model = vm.VozModel()
        self.t0 = 0
        self.k = 0          # muestra actual

    async def reset(self):
        d = self.dut
        cocotb.start_soon(make_clock(d).start())
        d.ena.value = 1
        d.ui_in.value = 0
        d.uio_in.value = 0
        d.rst_n.value = 0
        for _ in range(8):
            await FallingEdge(d.clk)
        d.rst_n.value = 1
        self.t0 = int(round(get_sim_time("ps")))    # flanco de bajada "-1/2"
        self.model.reset()
        self.k = 0

    async def at_cycle(self, m):
        """Espera hasta el flanco de bajada posterior al flanco de subida m."""
        target = self.t0 + (m + 1) * T_NS * 1000
        now = int(round(get_sim_time("ps")))
        if target > now:
            await Timer(target - now, "ps")

    async def write(self, base, addr, value):
        d = self.dut
        await self.at_cycle(base)
        d.ui_in.value = value & 0xFF
        d.uio_in.value = 0x80 | ((addr & 7) << 4) | ((value >> 8) & 0xF)
        await self.at_cycle(base + 4)
        d.uio_in.value = ((addr & 7) << 4) | ((value >> 8) & 0xF)

    async def sample(self, regs=()):
        """Avanza una muestra: el modelo calcula la muestra k, se escriben
        `regs` (efecto en la muestra k+1) y se compara la salida."""
        base = self.k * CYC
        self.model.step()
        for i, (a, v) in enumerate(regs):
            await self.write(base + 200 + 8 * i, a, v)
            self.model.write(a, v)
        await self.at_cycle(base + 600)
        uo = int(self.dut.uo_out.value)
        exp = ((self.model.out8 ^ 0x80) & 0xFF) >> 1
        got = uo >> 1
        assert got == exp, f"muestra {self.k}: chip {got} != modelo {exp}"
        if not GL:
            o8 = int(self.dut.user_project.out8.value)
            assert o8 == (self.model.out8 & 0xFF), f"muestra {self.k}: out8 {o8} != {self.model.out8 & 0xFF}"
        self.k += 1
        return self.model.out8

    async def frames(self, frames, spf):
        outs = []
        for fr in frames:
            regs = vm.frame_regs(fr)
            outs.append(await self.sample(regs))
            for _ in range(spf - 1):
                outs.append(await self.sample())
        return outs


@cocotb.test()
async def test_silencio_tras_reset(dut):
    h = Harness(dut)
    await h.reset()
    for _ in range(4):
        await h.sample()
    assert (int(dut.uo_out.value) >> 1) == 0x40, "con amplitud 0 la salida debe ser el punto medio"


@cocotb.test()
async def test_vocales(dut):
    """Las 5 vocales con el modelo: cada muestra debe coincidir."""
    h = Harness(dut)
    await h.reset()
    ms = 40 if GL else 120
    nz = 0
    for v in "aeiou":
        outs = await h.frames(ve.vocal_frames(v, ms=ms, f0=150), 8)
        nz += sum(1 for o in outs if o != 0)
    assert nz > 0.5 * h.k, "la salida casi no se movio"
    dut._log.info(f"{h.k} muestras iguales al modelo")


@cocotb.test()
async def test_registros_aleatorios(dut):
    """Frames aleatorios (coeficientes, pitch, amplitud, modo, atenuacion)."""
    h = Harness(dut)
    await h.reset()
    rnd = random.Random(2026)
    nfr = 6 if GL else 40
    for _ in range(nfr):
        regs = [(vm.REG_B1, rnd.randrange(4096)), (vm.REG_B2, rnd.randrange(4096)),
                (vm.REG_B3, rnd.randrange(4096)), (vm.REG_INC, rnd.randrange(1024)),
                (vm.REG_AMP, rnd.randrange(4096)), (rnd.randrange(5, 8), rnd.randrange(4096))]
        await h.sample(regs)
        for _ in range(rnd.randrange(3, 12)):
            await h.sample()
    dut._log.info(f"{h.k} muestras aleatorias iguales al modelo")


@cocotb.test()
async def test_frase_hola(dut):
    """Inicio de "Hola, IEEE" (0.3 s en RTL, recortado en GL). La frase
    completa se verifica en sim/make_wavs.py."""
    h = Harness(dut)
    await h.reset()
    fr = ve.texto_a_frames("Hola, IEEE")
    fr = fr[:6] if GL else fr[:60]
    await h.frames(fr, ve.SAMPLES_PER_FRAME if not GL else 6)
    dut._log.info(f"{h.k} muestras de la frase iguales al modelo")


@cocotb.test()
async def test_pdm(dut):
    """La densidad de unos del PDM sigue a la muestra de 8 bits."""
    h = Harness(dut)
    await h.reset()
    h.model.step()                      # muestra 0 (registros en cero)
    for a, v in vm.frame_regs(ve.vocal_frames("a", 100)[5]):
        await h.write(200 + 8 * a, a, v)
        h.model.write(a, v)
    for k in range(1, 30):
        await h.at_cycle(k * CYC + 61)  # out8 ya estable
        h.model.step()
        ones = 0
        n = 900
        for _ in range(n):
            await FallingEdge(dut.clk)
            ones += int(dut.uo_out.value) & 1
        u = (h.model.out8 ^ 0x80) & 0xFF
        assert abs(ones - u * n / 256) <= 6, f"densidad {ones}/{n} vs {u}/256"
