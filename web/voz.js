// Port a JavaScript de demo/voz_es.py y test/voz_model.py (bit-exacto).
(function (root) {
  'use strict';
  const FS = 10000000 / 1024, K = 4, PH = 13, FRAME_MS = 5, SPF = 49;
  const W = 14, S = 8, ACC_W = W + 3, CYCLES = 1024, LFSR_SLOT = 14;
  const VOZ = 1, RUIDO = 2, MIXTO = 3, SIL = 0;
  const R = Math.sqrt(1 - Math.pow(2, -K));

  function pyRound(x) {               // round() de Python (empate al par)
    const f = Math.floor(x), d = x - f;
    if (d > 0.5) return f + 1;
    if (d < 0.5) return f;
    return f % 2 === 0 ? f : f + 1;
  }
  function coef(f) {
    const b = pyRound(2 * R * Math.cos(2 * Math.PI * f / FS) * 1024);
    return Math.max(-2048, Math.min(2047, b));
  }
  function incPitch(f0) { return Math.max(0, Math.min(1023, pyRound(f0 * (1 << PH) / FS))); }

  const FON = {
    a: [750, 1300, 2500, 51, VOZ, 110, 'v', 0], e: [460, 1850, 2550, 57, VOZ, 100, 'v', 0],
    i: [290, 2250, 2950, 83, VOZ, 95, 'v', 1], o: [500, 900, 2450, 53, VOZ, 105, 'v', 2],
    u: [310, 750, 2350, 32, VOZ, 95, 'v', 3], l: [360, 1250, 2600, 21, VOZ, 60, 'a', 1],
    m: [270, 1050, 2300, 14, VOZ, 70, 'a', 2], n: [270, 1550, 2550, 17, VOZ, 65, 'a', 1],
    ny: [270, 1900, 2700, 27, VOZ, 80, 'a', 1], b: [300, 900, 2200, 10, VOZ, 50, 'a', 2],
    d: [320, 1500, 2500, 20, VOZ, 45, 'a', 1], g: [300, 1700, 2300, 19, VOZ, 50, 'a', 1],
    y: [280, 2150, 2800, 43, VOZ, 65, 'a', 1], r: [450, 1450, 2400, 21, VOZ, 25, 't', 0],
    rr: [450, 1450, 2400, 29, MIXTO, 90, 't', 0], s: [2600, 3300, 3700, 12, RUIDO, 100, 'f', 0],
    f: [1400, 2400, 3400, 30, RUIDO, 95, 'f', 0], j: [1100, 1900, 2700, 24, RUIDO, 95, 'f', 0],
    ch: [2100, 2800, 3500, 30, RUIDO, 70, 'f', 0], p: [700, 1100, 2400, 16, RUIDO, 15, 'p', 1],
    t: [1700, 2700, 3500, 49, RUIDO, 15, 'p', 0], k: [1300, 1900, 2600, 24, RUIDO, 20, 'p', 0],
    _: [500, 1500, 2500, 0, SIL, 120, 's', 0], '.': [500, 1500, 2500, 0, SIL, 250, 's', 0],
  };
  const DICC = { ieee: 'i triple e', tt: 'ti ti', rp2350: 'erre pe dos mil trescientos cincuenta', ok: 'okei', y: 'i' };
  const ACENTOS = { 'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u' };
  const VOC = 'aeiou';
  const NUM = ['cero', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve'];
  const inStr = (c, s) => c !== '' && s.indexOf(c) >= 0;

  function palabra(w0) {
    if (Object.prototype.hasOwnProperty.call(DICC, w0)) {
      let out = [];
      for (const p of DICC[w0].split(' ')) out = out.concat(palabra(p));
      return out;
    }
    let acento = -1, w = '';
    const chars = Array.from(w0);
    chars.forEach((c, i) => { if (inStr(c, 'áéíóú')) acento = i; w += ACENTOS[c] || c; });
    const wc = Array.from(w), n = wc.length, res = [];
    let i = 0;
    while (i < n) {
      const c = wc[i], nx = i + 1 < n ? wc[i + 1] : '';
      if (c === 'h') { i += 1; continue; }
      if (c === 'c' && nx === 'h') { res.push(['ch', i]); i += 2; continue; }
      if (c === 'l' && nx === 'l') { res.push(['y', i]); i += 2; continue; }
      if (c === 'r' && nx === 'r') { res.push(['rr', i]); i += 2; continue; }
      if (c === 'r') { res.push([i === 0 ? 'rr' : 'r', i]); i += 1; continue; }
      if (c === 'q') { res.push(['k', i]); i += nx === 'u' ? 2 : 1; continue; }
      if (c === 'g' && nx === 'u' && i + 2 < n && inStr(wc[i + 2], 'ei')) { res.push(['g', i]); i += 2; continue; }
      if (c === 'g' && (nx === 'e' || nx === 'i')) { res.push(['j', i]); i += 1; continue; }
      if (c === 'c') { res.push([(nx === 'e' || nx === 'i') ? 's' : 'k', i]); i += 1; continue; }
      if (c === 'z') { res.push(['s', i]); i += 1; continue; }
      if (c === 'v') { res.push(['b', i]); i += 1; continue; }
      if (c === 'ñ') { res.push(['ny', i]); i += 1; continue; }
      if (c === 'x') { res.push(['k', i]); res.push(['s', i]); i += 1; continue; }
      if (c === 'w') { res.push(['u', i]); i += 1; continue; }
      if (c === 'y') { res.push([(nx === '' || !inStr(nx, VOC)) ? 'i' : 'y', i]); i += 1; continue; }
      if (Object.prototype.hasOwnProperty.call(FON, c)) res.push([c, i]);
      i += 1;
    }
    const grupos = [];
    res.forEach(([f, pos], k) => {
      if (FON[f][6] !== 'v') return;
      const fuerte = inStr(f, 'aeo') || pos === acento;
      if (grupos.length && grupos[grupos.length - 1].slice(-1)[0] === k - 1) {
        const ant = res[k - 1][0];
        const antF = inStr(ant, 'aeo') || res[k - 1][1] === acento;
        if (!(fuerte && antF)) { grupos[grupos.length - 1].push(k); return; }
      }
      grupos.push([k]);
    });
    let ton = -1;
    if (acento >= 0) {
      res.forEach(([f, pos], k) => { if (pos === acento) ton = k; });
    } else if (grupos.length) {
      const ult = n ? wc[n - 1] : '';
      const g = ((inStr(ult, VOC) || inStr(ult, 'ns')) && grupos.length >= 2) ? grupos[grupos.length - 2] : grupos[grupos.length - 1];
      ton = g[g.length - 1];
      for (const k of g) if (inStr(res[k][0], 'aeo')) ton = k;
    }
    return res.map(([f], k) => [f, k === ton]);
  }

  const MAYUS = { 'Á': 'á', 'É': 'é', 'Í': 'í', 'Ó': 'ó', 'Ú': 'ú', 'Ü': 'ü', 'Ñ': 'ñ' };
  function textoAFonemas(texto) {
    const t = Array.from(texto).map(c => MAYUS[c] || c).join('').toLowerCase();
    let out = [], pal = '';
    for (const c of Array.from(t + ' ')) {
      if (/\p{L}/u.test(c) || /[0-9]/.test(c)) { pal += c; continue; }
      if (pal) {
        if (/^[0-9]+$/.test(pal)) { for (const d of pal) out = out.concat(palabra(NUM[+d])); }
        else out = out.concat(palabra(pal));
        pal = '';
      }
      if (inStr(c, ',;:')) out.push(['_', false]);
      else if (inStr(c, '.!?')) out.push(['.', false]);
    }
    while (out.length && inStr(out[out.length - 1][0], '_.')) out.pop();
    return out;
  }

  const lerp = (a, b, t) => a + (b - a) * t;
  function fonemasAFrames(fon, f0i = 135.0, f0f = 100.0, tasa = 1.0) {
    const durs = fon.map(([f, ton]) => Math.max(1, pyRound(FON[f][5] * (ton ? 1.3 : 1.0) / tasa / FRAME_MS)));
    const total = durs.reduce((a, b) => a + b, 0) || 1;
    const frames = [];
    let prev = null, prevSh = 0, pos = 0;
    fon.forEach(([f, ton], idx) => {
      const [F1, F2, F3, amp, modo, , clase, sh] = FON[f];
      const nf = durs[idx], tgt = [F1, F2, F3];
      const ini = (clase === 'p' || clase === 's' || prev === null) ? tgt : prev;
      const trans = Math.min(nf, 6);
      for (let k = 0; k < nf; k++) {
        const t = trans <= 1 ? 1.0 : Math.min(1.0, k / (trans - 1.0));
        const F = [0, 1, 2].map(q => lerp(ini[q], tgt[q], t));
        const f0 = lerp(f0i, f0f, (pos + k) / total) + (ton ? 18.0 : 0.0);
        let a = amp;
        const shf = k < trans ? Math.max(sh, prevSh) : sh;
        if (clase === 'p') {
          const cierre = Math.max(1, nf * 3);
          for (let q = 0; q < cierre; q++) frames.push([coef(F1), coef(F2), coef(F3), incPitch(f0), 0, SIL, sh]);
          for (let q = 0; q < nf; q++) frames.push([coef(F1), coef(F2), coef(F3), incPitch(f0), Math.trunc(amp * (1.0 - q / (nf + 1.0))), RUIDO, sh]);
          break;
        }
        if (clase === 't') a = (k % 4) < 2 ? amp : Math.floor(amp / 3);
        if (clase === 'v') {
          if (k === 0 && (idx === 0 || ['s', 'p', 'f'].includes(FON[fon[idx - 1][0]][6]))) a = Math.floor(amp / 2);
          if (k === nf - 1 && (idx === fon.length - 1 || FON[fon[idx + 1][0]][6] === 's')) a = Math.floor(amp / 2);
        }
        a = Math.min(255, a << (shf - sh));
        frames.push([coef(F[0]), coef(F[1]), coef(F[2]), incPitch(f0), a, modo, shf]);
      }
      prev = tgt; prevSh = sh; pos += nf;
    });
    for (let q = 0; q < 8; q++) frames.push([coef(500), coef(1500), coef(2500), incPitch(100), 0, SIL, 0]);
    return frames;
  }

  // ---------------------------------------------------------------- modelo del chip
  const sext = (v, bits) => { v &= (1 << bits) - 1; return (v >> (bits - 1)) ? v - (1 << bits) : v; };
  const sat = (v, bits) => { const hi = (1 << (bits - 1)) - 1, lo = -(1 << (bits - 1)); return v > hi ? hi : v < lo ? lo : v; };
  function mul12(c, yop) {
    let acc = 0;
    for (let i = 0; i < 12; i++) {
      let t = acc;
      if ((c >> i) & 1) t = i === 11 ? acc - yop : acc + yop;
      acc = t >> 1;
    }
    return acc;
  }
  const lfsrStep = s => ((s << 1) | (((s >> 14) ^ (s >> 13)) & 1)) & 0x7FFF;
  function jumpTable(n) {
    const cols = [];
    for (let b = 0; b < 15; b++) { let v = 1 << b; for (let q = 0; q < n; q++) v = lfsrStep(v); cols.push(v); }
    return cols;
  }
  const JS_ = jumpTable(CYCLES), JSLOT = jumpTable(LFSR_SLOT);
  const jump = (s, cols) => { let r = 0, b = 0; while (s) { if (s & 1) r ^= cols[b]; s >>= 1; b++; } return r; };

  class Chip {
    constructor() { this.reset(); }
    reset() { this.regs = [0, 0, 0, 0, 0, 0, 0, 0]; this.y1 = [0, 0, 0]; this.y2 = [0, 0, 0]; this.phase = 0; this.lfsr = jump(1, JSLOT); this.out8 = 0; this.src = 0; }
    write(a, v) {
      a &= 7;
      if (a === 2) this.regs[a] = (v & 0xFE0) | 0x010;
      else if (a <= 4) this.regs[a] = v & 0xFFF;
    }
    frame(fr) {
      const [b1, b2, b3, inc, amp, mode, sh] = fr;
      this.write(0, b1 & 0xFFF); this.write(1, b2 & 0xFFF); this.write(2, b3 & 0xFFF);
      this.write(3, inc & 0x3FF); this.write(4, ((sh & 3) << 10) | ((mode & 3) << 8) | (amp & 0xFF));
    }
    source() {
      const mode = (this.regs[4] >> 8) & 3;
      const saw = (this.phase >> (PH - S)) - (1 << (S - 1));
      const noise = sext(this.lfsr, S);
      const v = mode === 0 ? 0 : mode === 1 ? saw : mode === 2 ? noise : (saw ^ (noise >> 2));
      return v >> ((this.regs[4] >> 10) & 3);
    }
    step() {
      let x = this.source();
      this.src = x;
      for (let j = 0; j < 3; j++) {
        const b = this.regs[j], y1 = this.y1[j], y2 = this.y2[j];
        let a = mul12(b, y1 << 2) - y2 + (y2 >> K) + x;
        const yn = sat(sext(a, ACC_W), W);
        this.y2[j] = y1; this.y1[j] = yn; x = yn;
      }
      this.out8 = sat(sext(mul12(this.regs[4] & 0xFF, x << 2), ACC_W), 8);
      this.phase = (this.phase + (this.regs[3] & 0x3FF)) & ((1 << PH) - 1);
      this.lfsr = jump(this.lfsr, JS_);
      return this.out8;
    }
  }

  function render(frames, spf = SPF, warmup = 0) {
    const m = new Chip();
    for (let q = 0; q < warmup; q++) m.step();
    const out = new Int8Array(frames.length * spf), src = new Int16Array(frames.length * spf);
    let n = 0;
    for (const fr of frames) { m.frame(fr); for (let q = 0; q < spf; q++) { out[n] = m.step(); src[n] = m.src; n++; } }
    return { out, src };
  }

  const api = { FS, SPF, FON, coef, incPitch, textoAFonemas, fonemasAFrames, Chip, render };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.Voz = api;
})(typeof window !== 'undefined' ? window : globalThis);
