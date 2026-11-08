module peak_bin_detector (
  input logic clk, input logic rst_n,
  input logic s_valid, output logic s_ready,
  input logic [36:0] s_power, input logic [7:0] s_bin, input logic s_last,
  output logic m_valid, input logic m_ready,
  output logic signed [8:0] m_peak_bin, output logic [36:0] m_peak_power,
  output logic m_low_confidence
);
  logic [36:0] best_power, second_power;
  logic signed [8:0] best_bin, candidate_bin;
  logic candidate_allowed, candidate_wins;
  logic [36:0] final_best, final_second;
  logic [38:0] three_second;

  function automatic logic signed [8:0] signed_bin(input logic [7:0] raw_bin);
    signed_bin = raw_bin[7] ? $signed({1'b1, raw_bin}) : $signed({1'b0, raw_bin});
  endfunction

  assign s_ready = ~m_valid | m_ready;
  always_comb begin
    candidate_bin = signed_bin(s_bin);
    candidate_allowed = (candidate_bin != -1) && (candidate_bin != 0) &&
                        (candidate_bin != 1);
    candidate_wins = candidate_allowed && ((s_power > best_power) ||
      ((s_power == best_power) &&
       ((candidate_bin < 0 ? -candidate_bin : candidate_bin) <
        (best_bin < 0 ? -best_bin : best_bin))) ||
      ((s_power == best_power) &&
       ((candidate_bin < 0 ? -candidate_bin : candidate_bin) ==
        (best_bin < 0 ? -best_bin : best_bin)) && (candidate_bin < best_bin)));
    final_best = candidate_wins ? s_power : best_power;
    final_second = candidate_wins ? best_power :
                   ((candidate_allowed && s_power > second_power) ? s_power : second_power);
    three_second = {2'b0, final_second} + ({2'b0, final_second} << 1);
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      best_power <= 0; second_power <= 0; best_bin <= 9'sd127; m_valid <= 0;
      m_peak_bin <= 0; m_peak_power <= 0; m_low_confidence <= 0;
    end else begin
      if (m_valid && m_ready) m_valid <= 0;
      if (s_valid && s_ready) begin
        if (candidate_wins) begin
          second_power <= best_power; best_power <= s_power; best_bin <= candidate_bin;
        end else if (candidate_allowed && s_power > second_power) second_power <= s_power;
        if (s_last) begin
          m_valid <= 1;
          m_peak_power <= final_best;
          m_peak_bin <= candidate_wins ? candidate_bin : best_bin;
          m_low_confidence <= (final_best == 0) || ({2'b0, final_best} < three_second);
          best_power <= 0; second_power <= 0; best_bin <= 9'sd127;
        end
      end
    end
  end
endmodule
