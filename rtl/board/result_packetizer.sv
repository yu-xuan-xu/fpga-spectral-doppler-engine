module result_packetizer (
  input logic clk, input logic rst_n,
  input logic s_valid, output logic s_ready,
  input logic [7:0] s_case_id,
  input logic signed [8:0] s_peak_bin,
  input logic signed [23:0] s_frequency,
  input logic signed [19:0] s_velocity,
  input logic [36:0] s_peak_power,
  input logic [3:0] s_status,
  output logic m_valid, input logic m_ready, output logic [7:0] m_data
);
  logic [7:0] packet [0:19];
  logic [4:0] index;
  logic [15:0] crc, crc_next;
  logic active;
  crc16_ccitt crc_step(.crc_in(crc),.data(packet[index]),.crc_out(crc_next));
  assign s_ready = !active;
  assign m_valid = active;
  assign m_data = index == 18 ? crc[15:8] : index == 19 ? crc[7:0] : packet[index];
  always_ff @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin active<=0; index<=0; crc<=16'hffff; end
    else begin
      if(s_valid && s_ready) begin
        packet[0]<=8'ha5; packet[1]<=8'h5a; packet[2]<=8'h01; packet[3]<=s_case_id;
        packet[4]<={4'b0,s_status};
        packet[5]<={{7{s_peak_bin[8]}},s_peak_bin[8]}; packet[6]<=s_peak_bin[7:0];
        packet[7]<=s_frequency[23:16]; packet[8]<=s_frequency[15:8]; packet[9]<=s_frequency[7:0];
        packet[10]<={{4{s_velocity[19]}},s_velocity[19:16]}; packet[11]<=s_velocity[15:8];
        packet[12]<=s_velocity[7:0];
        packet[13]<={3'b0,s_peak_power[36:32]}; packet[14]<=s_peak_power[31:24];
        packet[15]<=s_peak_power[23:16]; packet[16]<=s_peak_power[15:8]; packet[17]<=s_peak_power[7:0];
        packet[18]<=0; packet[19]<=0;
        active<=1; index<=0; crc<=16'hffff;
      end else if(m_valid && m_ready) begin
        if(index<18) crc<=crc_next;
        if(index==19) begin active<=0; index<=0; end
        else index<=index+1'b1;
      end
    end
  end
endmodule
