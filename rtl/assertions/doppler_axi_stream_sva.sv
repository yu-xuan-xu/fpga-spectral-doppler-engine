// Icarus-compatible immediate assertions for the public AXI stream wrapper.
module doppler_axi_stream_sva #(
  parameter logic [31:0] RESULT_SEQUENCE_RESET_VALUE = 32'd0
) (
  input logic aclk,
  input logic aresetn,
  input logic [31:0] s_axis_tdata,
  input logic s_axis_tvalid,
  input logic s_axis_tready,
  input logic s_axis_tlast,
  input logic [127:0] m_axis_tdata,
  input logic m_axis_tvalid,
  input logic m_axis_tready,
  input logic m_axis_tlast,
  output logic [31:0] assertion_checked_cycles
);
  logic prior_input_stall, prior_output_stall;
  logic [31:0] prior_input_data;
  logic prior_input_last;
  logic [127:0] prior_output_data;
  logic prior_output_last;
  logic [31:0] prior_sequence;
  logic prior_output_transfer;
  logic prior_reset;
  logic reset_seen;
  logic [8:0] accepted_index;
  logic discarding;
  logic [31:0] legal_frame_count;
  logic [31:0] output_transfer_count;

  always_ff @(posedge aclk) begin
    if (!aresetn) begin
      if (reset_seen)
        assert (!m_axis_tvalid)
          else $fatal(1, "AXI output valid did not clear during reset");
      reset_seen <= 1'b1;
      prior_reset <= 1'b1;
      prior_input_stall <= 0;
      prior_output_stall <= 0;
      prior_input_data <= 0;
      prior_input_last <= 0;
      prior_output_data <= 0;
      prior_output_last <= 0;
      prior_sequence <= RESULT_SEQUENCE_RESET_VALUE;
      prior_output_transfer <= 0;
      accepted_index <= 0;
      discarding <= 0;
      legal_frame_count <= 0;
      output_transfer_count <= 0;
      assertion_checked_cycles <= 0;
    end else begin
      assertion_checked_cycles <= assertion_checked_cycles + 1'b1;
      reset_seen <= 0;
      if (prior_reset)
        assert (!m_axis_tvalid)
          else $fatal(1, "AXI output valid survived synchronous reset");
      prior_reset <= 0;

      if (prior_input_stall)
        assert (s_axis_tvalid && s_axis_tdata == prior_input_data &&
                s_axis_tlast == prior_input_last)
          else $fatal(1, "AXI input payload changed while stalled");
      if (prior_output_stall)
        assert (m_axis_tvalid && m_axis_tdata == prior_output_data &&
                m_axis_tlast == prior_output_last)
          else $fatal(1, "AXI output payload changed while stalled");

      assert (m_axis_tdata[31:0] ==
              (prior_sequence + (prior_output_transfer ? 32'd1 : 32'd0)))
        else $fatal(1, "result_sequence changed without exactly one output handshake");
      if (m_axis_tvalid) begin
        assert (m_axis_tlast)
          else $fatal(1, "single-beat AXI result did not assert TLAST");
        assert (m_axis_tdata[127:126] == 2'b00)
          else $fatal(1, "reserved AXI result bits are nonzero");
      end

      prior_sequence <= m_axis_tdata[31:0];
      prior_output_transfer <= m_axis_tvalid && m_axis_tready;
      prior_input_stall <= s_axis_tvalid && !s_axis_tready;
      if (s_axis_tvalid && !s_axis_tready) begin
        prior_input_data <= s_axis_tdata;
        prior_input_last <= s_axis_tlast;
      end
      prior_output_stall <= m_axis_tvalid && !m_axis_tready;
      if (m_axis_tvalid && !m_axis_tready) begin
        prior_output_data <= m_axis_tdata;
        prior_output_last <= m_axis_tlast;
      end

      if (s_axis_tvalid && s_axis_tready) begin
        if (discarding) begin
          if (s_axis_tlast) discarding <= 0;
        end else if (s_axis_tlast) begin
          if (accepted_index == 9'd255)
            legal_frame_count <= legal_frame_count + 1'b1;
          accepted_index <= 0;
        end else if (accepted_index == 9'd255) begin
          accepted_index <= 0;
          discarding <= 1;
        end else begin
          accepted_index <= accepted_index + 1'b1;
        end
      end

      if (m_axis_tvalid && m_axis_tready) begin
        assert (output_transfer_count < legal_frame_count)
          else $fatal(1, "AXI result has no accepted legal input frame");
        output_transfer_count <= output_transfer_count + 1'b1;
      end
    end
  end
endmodule

module doppler_axi_contract_top #(
  parameter logic [31:0] RESULT_SEQUENCE_RESET_VALUE = 32'd0
) (
  input logic aclk,
  input logic aresetn,
  input logic [31:0] s_axis_tdata,
  input logic s_axis_tvalid,
  output logic s_axis_tready,
  input logic s_axis_tlast,
  output logic [127:0] m_axis_tdata,
  output logic m_axis_tvalid,
  input logic m_axis_tready,
  output logic m_axis_tlast,
  output logic [31:0] assertion_checked_cycles
);
  doppler_axi_stream_wrapper #(
    .RESULT_SEQUENCE_RESET_VALUE(RESULT_SEQUENCE_RESET_VALUE)
  ) axi_wrapper (.*);
  doppler_axi_stream_sva #(
    .RESULT_SEQUENCE_RESET_VALUE(RESULT_SEQUENCE_RESET_VALUE)
  ) contract_checks (.*);
endmodule

module doppler_axi_equivalence_top (
  input logic aclk,
  input logic aresetn,
  input logic [31:0] s_axis_tdata,
  input logic s_axis_tvalid,
  output logic s_axis_tready,
  input logic s_axis_tlast,
  output logic [127:0] m_axis_tdata,
  output logic m_axis_tvalid,
  input logic m_axis_tready,
  output logic m_axis_tlast,
  output logic direct_s_ready,
  output logic direct_m_valid,
  output logic signed [8:0] direct_peak_bin,
  output logic signed [23:0] direct_frequency_q8_hz,
  output logic signed [19:0] direct_velocity_q8_mm_s,
  output logic [36:0] direct_peak_power,
  output logic [3:0] direct_status
);
  logic direct_resetn;

  always_ff @(posedge aclk) direct_resetn <= aresetn;

  doppler_axi_stream_wrapper axi_wrapper (.*);
  doppler_core direct_core (
    .clk(aclk),
    .rst_n(direct_resetn),
    .s_valid(s_axis_tvalid),
    .s_ready(direct_s_ready),
    .s_i($signed(s_axis_tdata[31:16])),
    .s_q($signed(s_axis_tdata[15:0])),
    .s_last(s_axis_tlast),
    .m_valid(direct_m_valid),
    .m_ready(m_axis_tready),
    .m_peak_bin(direct_peak_bin),
    .m_frequency_q8_hz(direct_frequency_q8_hz),
    .m_velocity_q8_mm_s(direct_velocity_q8_mm_s),
    .m_peak_power(direct_peak_power),
    .m_status(direct_status)
  );

  always_ff @(posedge aclk) begin
    if (aresetn)
      assert (s_axis_tready == direct_s_ready)
        else $fatal(1, "AXI wrapper changed canonical core input readiness");
  end
endmodule
