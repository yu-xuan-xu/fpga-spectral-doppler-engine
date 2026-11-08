module toolchain_smoke(output logic led);
  logic clk;
  logic [23:0] counter = 0;
  SB_HFOSC #(.CLKHF_DIV("0b10")) oscillator (.CLKHFPU(1'b1), .CLKHFEN(1'b1), .CLKHF(clk));
  always_ff @(posedge clk) counter <= counter + 1'b1;
  assign led = counter[23];
endmodule
