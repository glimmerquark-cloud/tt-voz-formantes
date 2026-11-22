// Testbench rapido (sin cocotb) para generar audio desde el RTL.
// Lee sim/build_wav/frames.hex: por frame 5 palabras {addr[2:0], dato[11:0]}
// y escribe una muestra de 8 bits (uo_out[7:1] y out8) por linea.
`timescale 1ns / 1ps
module tb_wav;
  reg clk = 0, rst_n = 0;
  reg [7:0] ui_in = 0, uio_in = 0;
  wire [7:0] uo_out, uio_out, uio_oe;
  tt_um_glimmerquark_voz dut (.ui_in(ui_in), .uo_out(uo_out), .uio_in(uio_in),
    .uio_out(uio_out), .uio_oe(uio_oe), .ena(1'b1), .clk(clk), .rst_n(rst_n));
  always #50 clk = ~clk;

  reg [14:0] mem [0:65535];
  integer nframes, spf, f, k, s, i, fd;
  reg [14:0] wv;

  task cyc(input integer n); integer q; begin for (q = 0; q < n; q = q + 1) @(negedge clk); end endtask

  initial begin
    if (!$value$plusargs("NF=%d", nframes)) nframes = 0;
    if (!$value$plusargs("SPF=%d", spf)) spf = 40;
    $readmemh("frames.hex", mem);
    fd = $fopen("samples.txt", "w");
    repeat (8) @(negedge clk);
    rst_n = 1;                       // flanco de subida siguiente = ranura 0
    // Lo escrito durante la muestra g se usa en la muestra g+1: se simula una
    // muestra extra y Python descarta la primera.
    for (k = 0; k <= nframes * spf; k = k + 1) begin
      f = k / spf;
      s = k % spf;
      begin
        cyc(200);                    // ranura ~200
        if (s == 0 && f < nframes) begin
          for (i = 0; i < 5; i = i + 1) begin
            wv = mem[f*5+i];
            ui_in = wv[7:0];
            uio_in = {1'b1, wv[14:12], wv[11:8]};
            cyc(4);
            uio_in = {1'b0, wv[14:12], wv[11:8]};
            cyc(4);
          end
          cyc(400 - 40);
        end else
          cyc(400);
        $fwrite(fd, "%0d\n", dut.out8);   // ranura ~600
        cyc(424);                    // total 1024 ciclos por muestra
      end
    end
    $fclose(fd);
    $finish;
  end
endmodule
