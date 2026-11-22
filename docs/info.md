<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

A **formant speech synthesizer that speaks Spanish**. The work is split between the chip and the RP2350 on the Tiny Tapeout board:

- **The RP2350** turns text into phonemes. Spanish spelling is almost phonetic, so simple rules are enough. It then sends a "frame" every ~5 ms: the three formant coefficients, pitch, amplitude and the source type.
- **The chip** does all the audio processing in real time at **fs = 10 MHz / 1024 = 9765.6 Hz**:

```
 source ──► F1 resonator ──► F2 resonator ──► F3 resonator ──► × amplitude ──► 8-bit sample ──► sigma-delta ──► AUDIO_PDM
 (sawtooth at F0 / LFSR noise / mix,  attenuation 2^-sh)
```

- **Source.** A 13-bit phase accumulator generates a sawtooth at the pitch F0, for voiced sounds. A 15-bit LFSR generates noise, for fricatives and plosive bursts. Mode 3 mixes both, for the trilled "rr".
- **Resonators.** Three 2-pole IIR filters in cascade:
  `y[n] = B·y[n-1] − (1 − 2⁻⁴)·y[n-2] + x[n]`
  - `B = 2r·cos(2πF/fs)` sets the formant frequency.
  - The bandwidth is fixed at about 97 Hz, so `r²` is a constant. That makes `r²·y` a simple shift-and-subtract.
  - The states are 14 bits, with saturation.
- **Shared datapath.** All four multiplications per sample (B1·y, B2·y, B3·y and amplitude·y) run on **one serial shift-add multiplier** (12 cycles each) and one 17-bit adder. The state words rotate through a 3-entry ring, so no read multiplexers are needed.
- **Schedule.** One sample takes 62 of the 1024 clock cycles available.
- **Audio output.** A 1st-order sigma-delta modulator running at 10 MHz turns the 8-bit sample into a 1-bit PDM stream on `uo[0]`. The upper 7 bits of the sample are also available on `uo[7:1]` (offset binary) for debugging or for an external DAC.

### Register interface

To write a register:
1. Put the 12-bit data on `{uio[3:0], ui[7:0]}` and the address on `uio[6:4]`.
2. Raise `uio[7]` (WR_STROBE) for at least 3 clock cycles.

The strobe is synchronized inside the chip.

| addr | register | format |
|---|---|---|
| 0 | B1 (F1) | signed Q2.10, `round(2r·cos(2πF1/fs)·1024)`, `r = sqrt(1−2⁻⁴)` |
| 1 | B2 (F2) | same as B1 |
| 2 | B3 (F3) | same as B1; only bits [11:5] are kept (≈25 Hz resolution) |
| 3 | pitch | 10 bits, `F0 = inc · fs / 8192` (≈1.19 Hz steps) |
| 4 | amp / mode | [7:0] amplitude, [9:8] source mode (0 silence, 1 voice, 2 noise, 3 mixed), [11:10] source attenuation 2^-sh |

After reset the amplitude is 0, so the chip is silent.

## How to test

1. Select the design, set the clock to **10 MHz** and release reset.
2. Run `demo/main_voz.py` from this repository on the board's MicroPython. It drives the register interface from the RP2350 and contains the text-to-phoneme rules. Type any Spanish text and the chip speaks it:
   ```python
   import main_voz
   main_voz.decir("Hola, IEEE")
   ```
3. Listen to `uo[0]` (AUDIO_PDM) through an RC low-pass filter (see below). `uo[7:1]` shows the sample for a logic analyzer or R-2R DAC.

The simulation WAVs in `wav/` (`hola_ieee.wav`, `vocales.wav`, `presentacion.wav`) are generated from the RTL itself, and they match the bit-exact Python model (`test/voz_model.py`) sample by sample.

## External hardware

- An RC low-pass filter on `uo[0]`, e.g. 1 kΩ + 47 nF (fc ≈ 3.4 kHz), better as two stages.
- A small audio amplifier (PAM8302, LM386) and a speaker, or active PC speakers.
