"""Genera WAVs desde la simulacion RTL (Icarus) y los verifica contra el modelo.

Uso:  python sim/make_wavs.py      -> wav/*.wav
"""
from pathlib import Path
import shutil, subprocess, sys, wave

root = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(root / "test"), str(root / "demo")]
import voz_model as vm   # noqa: E402
import voz_es as ve      # noqa: E402

FRASES = {
    "hola_ieee": "Hola, IEEE",
    "vocales": "a, e, i, o, u",
    "presentacion": "Hola, soy un chip de silicio que habla español.",
}

build = root / "sim" / "build_wav"
outdir = root / "wav"


def to_wav(path, samples, fs=9766):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(fs)
        w.writeframes(b"".join(int(max(-32768, min(32767, s * 256))).to_bytes(2, "little", signed=True)
                               for s in samples))


def main():
    build.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(exist_ok=True)
    vvp = build / "tb_wav.vvp"
    subprocess.run(["iverilog", "-g2012", "-o", str(vvp), str(root / "src" / "project.v"),
                    str(root / "sim" / "tb_wav.v")], check=True)
    sel = sys.argv[1:] or list(FRASES)
    for name in sel:
        txt = FRASES[name]
        frames = ve.texto_a_frames(txt)
        with open(build / "frames.hex", "w") as f:
            for fr in frames:
                for a, v in vm.frame_regs(fr):
                    f.write("%04x\n" % ((a << 12) | v))
        subprocess.run(["vvp", "-n", str(vvp), "+NF=%d" % len(frames), "+SPF=%d" % ve.SAMPLES_PER_FRAME],
                       cwd=build, check=True, stdout=subprocess.DEVNULL)
        rtl = [vm.sext(int(l), 8) for l in open(build / "samples.txt")][1:]
        ref = vm.render(frames, ve.SAMPLES_PER_FRAME, warmup=1)
        bad = sum(1 for a, b in zip(rtl, ref) if a != b) + abs(len(rtl) - len(ref))
        to_wav(outdir / f"{name}.wav", rtl)
        print(f"{name}: {len(rtl)} muestras ({len(rtl)/vm.FS:.2f} s), diferencias RTL/modelo = {bad}")
        if bad:
            sys.exit(1)


if __name__ == "__main__":
    main()
