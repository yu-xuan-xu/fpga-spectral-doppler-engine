module window_multiplier (
  input logic clk, input logic rst_n,
  input logic s_valid, output logic s_ready,
  input logic signed [17:0] s_i, input logic signed [17:0] s_q, input logic s_last,
  output logic m_valid, input logic m_ready,
  output logic signed [15:0] m_i, output logic signed [15:0] m_q, output logic m_last
);
  logic [7:0] index;
  logic signed [33:0] product_i, product_q;
  logic signed [18:0] rounded_i, rounded_q;
`include "hann_q15.svh"

  function automatic logic signed [15:0] sat16(input logic signed [18:0] value);
    if (value > 19'sd32767) sat16 = 16'sd32767;
    else if (value < -19'sd32768) sat16 = -16'sd32768;
    else sat16 = value[15:0];
  endfunction

  function automatic logic signed [18:0] round_q15(input logic signed [33:0] value);
    logic signed [33:0] magnitude;
    begin
      magnitude = value < 0 ? -value : value;
      round_q15 = value < 0 ? -((magnitude + 34'sd16384) >>> 15) :
                              ((magnitude + 34'sd16384) >>> 15);
    end
  endfunction

  assign s_ready = ~m_valid | m_ready;
  always_comb begin
    product_i = s_i * $signed({1'b0, hann_coeff(index)});
    product_q = s_q * $signed({1'b0, hann_coeff(index)});
    rounded_i = round_q15(product_i);
    rounded_q = round_q15(product_q);
  end
  always_ff @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin index<=0; m_valid<=0; m_i<=0; m_q<=0; m_last<=0; end
    else if(s_ready) begin
      m_valid<=s_valid;
      if(s_valid) begin
        m_i<=sat16(rounded_i); m_q<=sat16(rounded_q); m_last<=s_last;
        index<=s_last ? 0 : index+1'b1;
      end
    end
  end
endmodule
