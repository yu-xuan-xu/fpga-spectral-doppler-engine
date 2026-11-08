module doppler_resource_top(output logic signature);
  logic clk,rst_n=0; logic [5:0] reset_count=0; logic [7:0] sample_count=0;
  logic s_ready,m_valid; logic signed [8:0] peak_bin; logic signed [23:0] frequency;
  logic signed [19:0] velocity; logic [36:0] peak_power; logic [3:0] status;
  SB_HFOSC #(.CLKHF_DIV("0b10")) oscillator(.CLKHFPU(1'b1),.CLKHFEN(1'b1),.CLKHF(clk));
  always_ff @(posedge clk) begin
    reset_count<=reset_count+!reset_count[5]; rst_n<=reset_count[5];
    if(rst_n && s_ready) sample_count<=sample_count+1'b1;
  end
  doppler_core core(.clk,.rst_n,.s_valid(rst_n),.s_ready,
    .s_i({1'b0,sample_count,7'b0}),.s_q('0),.s_last(sample_count==8'hff),
    .m_valid,.m_ready(1'b1),.m_peak_bin(peak_bin),.m_frequency_q8_hz(frequency),
    .m_velocity_q8_mm_s(velocity),.m_peak_power(peak_power),.m_status(status));
  assign signature=^{peak_bin,frequency,velocity,peak_power,status,m_valid};
endmodule
