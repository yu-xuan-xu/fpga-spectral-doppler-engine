module sync_ram_256x16 (
  input logic clk,
  input logic we,
  input logic [7:0] addr,
  input logic signed [15:0] wdata,
  output logic signed [15:0] rdata
);
  logic signed [15:0] memory [0:255];
  always_ff @(posedge clk) begin
    if (we) memory[addr] <= wdata;
    else rdata <= memory[addr];
  end
endmodule
