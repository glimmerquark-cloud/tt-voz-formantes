![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg)

# Sintetizador de voz por formantes que habla español — Tiny Tapeout GF180

Tile 1x1 (GF180) que sintetiza voz en tiempo real.

**Pruébalo en el navegador:** [página que habla](https://htmlpreview.github.io/?https://github.com/glimmerquark-cloud/tt-voz-formantes/blob/main/web/chip_que_habla.html). Escribe un texto y el modelo bit-exacto del chip lo sintetiza ahí mismo.

**Del lado de la tarjeta.** El RP2350 convierte texto en fonemas y manda un frame cada 5 ms con F1/F2/F3, pitch, amplitud y tipo de fuente.

**Del lado del chip:**
- Diente de sierra glotal o ruido LFSR.
- 3 resonadores IIR en cascada que comparten un solo multiplicador serial.
- Modulador sigma-delta: la salida de audio ocupa un solo pin.

| Archivo | Qué es |
|---|---|
| `src/project.v` | RTL (`tt_um_glimmerquark_voz`) |
| `test/voz_model.py` | modelo Python bit-exacto |
| `test/test.py` | pruebas cocotb RTL contra el modelo |
| `demo/voz_es.py` | texto en español → fonemas → frames (CPython y MicroPython) |
| `demo/main_voz.py` | demo para la tarjeta Tiny Tapeout |
| `sim/make_wavs.py` | genera `wav/*.wav` desde la simulación RTL y lo verifica contra el modelo |
| `web/chip_que_habla.html` | página interactiva (se genera con `python web/build.py`) |
| `docs/info.md` | hoja de datos |

## Correr localmente (Windows, sin make)

```
python sim/run_tests.py     # pruebas cocotb
python sim/make_wavs.py     # WAVs desde el RTL
```

Requisitos: OSS CAD Suite (iverilog) en el PATH y `pip install cocotb==2.1.0`.
