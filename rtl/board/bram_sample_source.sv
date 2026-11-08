module bram_sample_source #(
  parameter MEM_FILE = "testvectors/canonical/steady_pos_bin16/input_iq_q15.mem",
  parameter integer FRAME_INDEX = 1
) (
  input logic clk,
  input logic rst_n,
  input logic start,
  output logic busy,
  output logic s_valid,
  input logic s_ready,
  output logic signed [15:0] s_i,
  output logic signed [15:0] s_q,
  output logic s_last
);
  logic [31:0] memory [0:1023];
  logic [7:0] index;
  logic [31:0] sample;
  initial $readmemh(MEM_FILE, memory);
  always_comb begin
    sample = memory[FRAME_INDEX*256 + index];
    s_i = sample[31:16];
    s_q = sample[15:0];
    s_last = index == 8'hff;
    s_valid = busy;
  end
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin busy <= 0; index <= 0; end
    else begin
      if (start && !busy) begin busy <= 1; index <= 0; end
      else if (s_valid && s_ready) begin
        if (s_last) begin busy <= 0; index <= 0; end
        else index <= index + 1'b1;
      end
    end
  end
endmodule
