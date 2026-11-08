module dc_wall_filter (
  input  logic clk,
  input  logic rst_n,
  input  logic s_valid,
  output logic s_ready,
  input  logic signed [15:0] s_i,
  input  logic signed [15:0] s_q,
  input  logic s_last,
  output logic m_valid,
  input  logic m_ready,
  output logic signed [17:0] m_i,
  output logic signed [17:0] m_q,
  output logic m_last,
  output logic overflow
);
  logic signed [15:0] prev_x_i, prev_x_q;
  logic signed [17:0] prev_y_i, prev_y_q;
  logic signed [20:0] wide_i, wide_q;

  function automatic logic signed [17:0] sat18(input logic signed [20:0] value);
    if (value > 21'sd131071) sat18 = 18'sd131071;
    else if (value < -21'sd131072) sat18 = -18'sd131072;
    else sat18 = value[17:0];
  endfunction

  function automatic logic signed [20:0] round_shift6(input logic signed [24:0] value);
    logic signed [24:0] magnitude;
    begin
      magnitude = value < 0 ? -value : value;
      round_shift6 = value < 0 ? -((magnitude + 25'sd32) >>> 6) :
                                 ((magnitude + 25'sd32) >>> 6);
    end
  endfunction

  assign s_ready = ~m_valid | m_ready;
  always_comb begin
    wide_i = $signed(s_i) - $signed(prev_x_i) +
             round_shift6(($signed(prev_y_i) <<< 6) - $signed(prev_y_i));
    wide_q = $signed(s_q) - $signed(prev_x_q) +
             round_shift6(($signed(prev_y_q) <<< 6) - $signed(prev_y_q));
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      prev_x_i <= '0; prev_x_q <= '0; prev_y_i <= '0; prev_y_q <= '0;
      m_valid <= 1'b0; m_i <= '0; m_q <= '0; m_last <= 1'b0; overflow <= 1'b0;
    end else if (s_ready) begin
      m_valid <= s_valid;
      if (s_valid) begin
        m_i <= sat18(wide_i); m_q <= sat18(wide_q); m_last <= s_last;
        overflow <= (wide_i > 21'sd131071) || (wide_i < -21'sd131072) ||
                    (wide_q > 21'sd131071) || (wide_q < -21'sd131072);
        prev_x_i <= s_i; prev_x_q <= s_q;
        prev_y_i <= sat18(wide_i); prev_y_q <= sat18(wide_q);
      end
    end
  end
endmodule
