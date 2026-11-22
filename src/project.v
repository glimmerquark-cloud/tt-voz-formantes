/*
 * Copyright (c) 2026 Irvin Ariel Madrid Castillo
 * SPDX-License-Identifier: Apache-2.0
 *
 * Sintetizador de voz por formantes (espanol) para Tiny Tapeout GF180.
 *
 *   fuente (diente de sierra / ruido LFSR) -> F1 -> F2 -> F3 -> x amplitud
 *   -> muestra de 8 bits -> modulador sigma-delta de 1er orden (1 pin de audio)
 *
 * Cada resonador:  y[n] = B*y[n-1] - (1-2^-K)*y[n-2] + x[n]
 * Los tres resonadores y la amplitud comparten UN multiplicador serial
 * (shift-add, 12 ciclos) y UN sumador de 17 bits. Con reloj de 10 MHz hay
 * 1024 ciclos por muestra (fs = 9765.6 Hz); el calculo usa los primeros 62.
 *
 * Escritura de registros (desde el RP2350):
 *   uio_in[7]   strobe (flanco de subida, se sincroniza dentro)
 *   uio_in[6:4] direccion
 *   uio_in[3:0] dato[11:8]
 *   ui_in[7:0]  dato[7:0]
 *   0: B1  1: B2  2: B3   (Q2.10 con signo, B = 2 r cos(2 pi F / fs))
 *      B3 guarda solo dato[11:5] (resolucion ~25 Hz)
 *   3: incremento de fase del pitch (10 bits, F0 = inc * fs / 8192)
 *   4: [7:0] amplitud, [9:8] modo (0 silencio, 1 voz, 2 ruido, 3 mixto),
 *      [11:10] atenuacion de la fuente 2^-sh
 *
 * Salidas: uo_out[0] = audio PDM, uo_out[7:1] = muestra (binario desplazado).
 */

`default_nettype none

module tt_um_glimmerquark_voz (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

  localparam W     = 14;      // estados de los resonadores
  localparam AW    = W + 3;   // acumulador
  localparam PH    = 13;      // fase del pitch
  localparam S     = 8;       // bits de la fuente
  localparam K     = 4;       // r^2 = 1 - 2^-K

  // ------------------------------------------------------------------
  // Interfaz de registros
  // ------------------------------------------------------------------
  reg [2:0] stb;
  wire      we = stb[1] & ~stb[2];
  wire [11:0] wdata = {uio_in[3:0], ui_in};
  wire [2:0]  waddr = uio_in[6:4];

  reg [11:0] b1, b2;
  reg [6:0]  b3;
  reg [9:0]  inc;
  reg [7:0]  amp;
  reg [1:0]  mode;
  reg [1:0]  sh;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      stb  <= 3'b0;
      b1   <= 12'd0;
      b2   <= 12'd0;
      b3   <= 7'd0;
      inc  <= 10'd0;
      amp  <= 8'd0;
      mode <= 2'd0;
      sh   <= 2'd0;
    end else begin
      stb <= {stb[1:0], uio_in[7]};
      if (we) begin
        case (waddr)
          3'd0: b1 <= wdata;
          3'd1: b2 <= wdata;
          3'd2: b3 <= wdata[11:5];
          3'd3: inc <= wdata[9:0];
          3'd4: {sh, mode, amp} <= wdata;
          default: ;
        endcase
      end
    end
  end

  // ------------------------------------------------------------------
  // Secuenciador: cnt = 0..1023.  cnt[5:4] = j (0..2 resonadores, 3 = salida)
  // st = cnt[3:0]: 0..11 multiplicacion, 12..15 sumas / escritura
  // ------------------------------------------------------------------
  reg [9:0]  cnt;
  wire       busy  = (cnt[9:6] == 4'd0);     // 0..63
  wire [1:0] j     = cnt[5:4];
  wire [3:0] st    = cnt[3:0];
  wire       mstep = busy & (st < 4'd12);
  wire       resn  = busy & (j != 2'd3);

  // ------------------------------------------------------------------
  // Estados: anillo de 3 pares (y1, y2). La cabeza P0 es el resonador actual.
  // ------------------------------------------------------------------
  reg signed [W-1:0] p0y1, p0y2, p1y1, p1y2, p2y1, p2y2;

  // ------------------------------------------------------------------
  // Fuente
  // ------------------------------------------------------------------
  reg [PH-1:0] phase;
  reg [14:0]   lfsr;
  wire signed [S-1:0] saw   = {~phase[PH-1], phase[PH-2:PH-S]};
  wire signed [S-1:0] noise = lfsr[S-1:0];
  reg  signed [S-1:0] src0;
  always @(*) begin
    case (mode)
      2'd0: src0 = {S{1'b0}};
      2'd1: src0 = saw;
      2'd2: src0 = noise;
      default: src0 = saw ^ (noise >>> 2);
    endcase
  end
  wire signed [S-1:0] src = src0 >>> sh;

  // ------------------------------------------------------------------
  // Multiplicador serial + sumador compartido
  // ------------------------------------------------------------------
  reg  signed [AW-1:0] acc;
  reg  [11:0] coef;
  always @(*) begin
    case (j)
      2'd0: coef = b1;
      2'd1: coef = b2;
      2'd2: coef = {b3, 5'b10000};
      default: coef = {4'd0, amp};
    endcase
  end
  wire mbit = coef[st];

  wire signed [W-1:0]  mop  = (j == 2'd3) ? p2y1 : p0y1;
  wire signed [AW-1:0] yop  = {{(AW-W-2){mop[W-1]}}, mop, 2'b00};
  wire signed [W-1:0]  xin  = (j == 2'd0) ? {{(W-S){src[S-1]}}, src} : p2y1;

  reg  signed [AW-1:0] addend;
  reg                  cin;
  always @(*) begin
    addend = {AW{1'b0}};
    cin    = 1'b0;
    if (st < 4'd12) begin
      if (mbit) begin
        if (st == 4'd11) begin
          addend = ~yop;
          cin    = 1'b1;
        end else begin
          addend = yop;
        end
      end
    end else begin
      case (st[1:0])
        2'd0: begin addend = ~{{(AW-W){p0y2[W-1]}}, p0y2}; cin = 1'b1; end
        2'd1: addend = {{(AW-W+K){p0y2[W-1]}}, p0y2[W-1:K]};
        2'd2: addend = {{(AW-W){xin[W-1]}}, xin};
        default: ;
      endcase
    end
  end

  wire signed [AW-1:0] acc_in = (st == 4'd0) ? {AW{1'b0}} : acc;
  wire signed [AW-1:0] sum    = acc_in + addend + {{(AW-1){1'b0}}, cin};

  // Saturacion a W bits y a 8 bits
  wire ovf_w = ~((&acc[AW-1:W-1]) | ~(|acc[AW-1:W-1]));
  wire signed [W-1:0] acc_sat = ovf_w ? {acc[AW-1], {(W-1){~acc[AW-1]}}} : acc[W-1:0];
  wire ovf_8 = ~((&acc[AW-1:7]) | ~(|acc[AW-1:7]));
  wire [7:0] out_sat = ovf_8 ? {acc[AW-1], {7{~acc[AW-1]}}} : acc[7:0];

  // ------------------------------------------------------------------
  // Salida y sigma-delta
  // ------------------------------------------------------------------
  reg [7:0] out8;      // muestra con signo
  reg [7:0] sd;
  reg       pdm;
  wire [7:0] uout = out8 ^ 8'h80;
  wire [8:0] sd_sum = {1'b0, sd} + {1'b0, uout};

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      cnt   <= 10'd0;
      p0y1  <= {W{1'b0}};
      p0y2  <= {W{1'b0}};
      p1y1  <= {W{1'b0}};
      p1y2  <= {W{1'b0}};
      p2y1  <= {W{1'b0}};
      p2y2  <= {W{1'b0}};
      phase <= {PH{1'b0}};
      lfsr  <= 15'd1;
      out8  <= 8'd0;
      sd    <= 8'd0;
      pdm   <= 1'b0;
    end else begin
      cnt <= cnt + 10'd1;

      if (resn && st == 4'd15) begin
        p0y1 <= p1y1;
        p0y2 <= p1y2;
        p1y1 <= p2y1;
        p1y2 <= p2y2;
        p2y1 <= acc_sat;
        p2y2 <= p0y1;
      end

      if (busy && j == 2'd3 && st == 4'd12)
        out8 <= out_sat;
      if (busy && j == 2'd3 && st == 4'd13)
        phase <= phase + {{(PH-10){1'b0}}, inc};
      lfsr <= {lfsr[13:0], lfsr[14] ^ lfsr[13]};   // avanza en cada ciclo

      {pdm, sd} <= sd_sum;
    end
  end

  // Acumulador: sin reset (se limpia al inicio de cada multiplicacion)
  always @(posedge clk) begin
    // fuera de las ranuras utiles el valor no importa: st == 0 lo reinicia
    acc <= mstep ? (sum >>> 1) : sum;
  end

  assign uo_out  = {uout[7:1], pdm};
  assign uio_out = 8'd0;
  assign uio_oe  = 8'd0;

  wire _unused = &{ena, 1'b0};

endmodule
