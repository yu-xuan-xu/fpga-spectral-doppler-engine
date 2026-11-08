module doppler_axi_stream_wrapper #(
  parameter logic [31:0] RESULT_SEQUENCE_RESET_VALUE = 32'd0
) (
  input  logic         aclk,
  input  logic         aresetn,
  input  logic [31:0]  s_axis_tdata,
  input  logic         s_axis_tvalid,
  output logic         s_axis_tready,
  input  logic         s_axis_tlast,
  output logic [127:0] m_axis_tdata,
  output logic         m_axis_tvalid,
  input  logic         m_axis_tready,
  output logic         m_axis_tlast
);
  logic core_resetn;
  logic core_result_valid, core_result_ready;
  logic signed [8:0] core_peak_bin;
  logic signed [23:0] core_frequency_q8_hz;
  logic signed [19:0] core_velocity_q8_mm_s;
  logic [36:0] core_peak_power;
  logic [3:0] core_status;
  logic [31:0] result_sequence;

  // aresetn is sampled synchronously. The registered value drives the existing
  // core's active-low asynchronous reset input without changing core RTL.
  always_ff @(posedge aclk) begin
    core_resetn <= aresetn;
    if (!aresetn)
      result_sequence <= RESULT_SEQUENCE_RESET_VALUE;
    else if (m_axis_tvalid && m_axis_tready)
      result_sequence <= result_sequence + 1'b1;
  end

  doppler_core core (
    .clk(aclk),
    .rst_n(core_resetn),
    .s_valid(s_axis_tvalid),
    .s_ready(s_axis_tready),
    .s_i($signed(s_axis_tdata[31:16])),
    .s_q($signed(s_axis_tdata[15:0])),
    .s_last(s_axis_tlast),
    .m_valid(core_result_valid),
    .m_ready(core_result_ready),
    .m_peak_bin(core_peak_bin),
    .m_frequency_q8_hz(core_frequency_q8_hz),
    .m_velocity_q8_mm_s(core_velocity_q8_mm_s),
    .m_peak_power(core_peak_power),
    .m_status(core_status)
  );

  assign core_result_ready = m_axis_tready;
  assign m_axis_tvalid = core_result_valid;
  assign m_axis_tlast = 1'b1;

  always_comb begin
    m_axis_tdata = '0;
    m_axis_tdata[31:0] = result_sequence;
    m_axis_tdata[40:32] = core_peak_bin;
    m_axis_tdata[64:41] = core_frequency_q8_hz;
    m_axis_tdata[84:65] = core_velocity_q8_mm_s;
    m_axis_tdata[121:85] = core_peak_power;
    m_axis_tdata[125:122] = core_status;
    m_axis_tdata[127:126] = 2'b00;
  end
endmodule
