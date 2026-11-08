module velocity_mapper (
  input logic clk, input logic rst_n,
  input logic s_valid, output logic s_ready,
  input logic signed [8:0] s_peak_bin, input logic [36:0] s_peak_power,
  input logic [3:0] s_status,
  output logic m_valid, input logic m_ready,
  output logic signed [23:0] m_frequency_q8_hz,
  output logic signed [19:0] m_velocity_q8_mm_s,
  output logic signed [8:0] m_peak_bin, output logic [36:0] m_peak_power,
  output logic [3:0] m_status
);
  assign s_ready = ~m_valid | m_ready;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      m_valid <= 0; m_frequency_q8_hz <= 0; m_velocity_q8_mm_s <= 0;
      m_peak_bin <= 0; m_peak_power <= 0; m_status <= 0;
    end else if (s_ready) begin
      m_valid <= s_valid;
      if (s_valid) begin
        // 20000 = 16384 + 2048 + 1024 + 512 + 32; 3080 = 2048 + 1024 + 8.
        m_frequency_q8_hz <= ($signed(s_peak_bin) <<< 14) + ($signed(s_peak_bin) <<< 11) +
                            ($signed(s_peak_bin) <<< 10) + ($signed(s_peak_bin) <<< 9) +
                            ($signed(s_peak_bin) <<< 5);
        m_velocity_q8_mm_s <= ($signed(s_peak_bin) <<< 11) + ($signed(s_peak_bin) <<< 10) +
                              ($signed(s_peak_bin) <<< 3);
        m_peak_bin <= s_peak_bin; m_peak_power <= s_peak_power; m_status <= s_status;
      end
    end
  end
endmodule
