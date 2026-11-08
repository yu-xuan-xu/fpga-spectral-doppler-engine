module board_top(output logic uart_tx_pin, output logic done_pin);
  logic clk,rst_n=0; logic [5:0] reset_count=0; logic start,source_busy;
  logic s_valid,s_ready,s_last; logic signed [15:0] s_i,s_q;
  logic m_valid,m_ready; logic signed [8:0] peak_bin; logic signed [23:0] frequency;
  logic signed [19:0] velocity; logic [36:0] peak_power; logic [3:0] status;
  logic packet_valid,packet_ready; logic [7:0] packet_data; logic uart_busy;
  logic started,packet_seen;
  SB_HFOSC #(.CLKHF_DIV("0b10")) oscillator(.CLKHFPU(1'b1),.CLKHFEN(1'b1),.CLKHF(clk));
  always_ff @(posedge clk) begin
    reset_count<=reset_count+!reset_count[5]; rst_n<=reset_count[5];
    if(!rst_n) begin started<=0; packet_seen<=0; done_pin<=0; end
    else begin
      if(start) started<=1;
      if(packet_valid) packet_seen<=1;
      if(packet_seen && !packet_valid && !uart_busy) done_pin<=1;
    end
  end
  assign start=rst_n && !started;
  bram_sample_source source(.clk,.rst_n,.start,.busy(source_busy),.s_valid,.s_ready,.s_i,.s_q,.s_last);
  doppler_core core(.clk,.rst_n,.s_valid,.s_ready,.s_i,.s_q,.s_last,.m_valid,.m_ready,
    .m_peak_bin(peak_bin),.m_frequency_q8_hz(frequency),.m_velocity_q8_mm_s(velocity),
    .m_peak_power(peak_power),.m_status(status));
  result_packetizer packetizer(.clk,.rst_n,.s_valid(m_valid),.s_ready(m_ready),.s_case_id(8'h01),
    .s_peak_bin(peak_bin),.s_frequency(frequency),.s_velocity(velocity),.s_peak_power(peak_power),
    .s_status(status),.m_valid(packet_valid),.m_ready(packet_ready),.m_data(packet_data));
  uart_tx uart(.clk,.rst_n,.s_valid(packet_valid),.s_ready(packet_ready),.s_data(packet_data),
    .tx(uart_tx_pin),.busy(uart_busy));
endmodule
