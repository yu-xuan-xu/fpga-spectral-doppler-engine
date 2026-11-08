// Icarus-compatible public-interface assertions for the Doppler stream contract.
module doppler_stream_sva (
  input logic clk,
  input logic rst_n,
  input logic s_valid,
  input logic s_ready,
  input logic signed [15:0] s_i,
  input logic signed [15:0] s_q,
  input logic s_last,
  input logic m_valid,
  input logic m_ready,
  input logic signed [8:0] m_peak_bin,
  input logic signed [23:0] m_frequency_q8_hz,
  input logic signed [19:0] m_velocity_q8_mm_s,
  input logic [36:0] m_peak_power,
  input logic [3:0] m_status,
  output logic [31:0] checked_cycles
);
  logic [8:0] accepted_index;
  logic discarding;
  logic [31:0] legal_frame_count;
  logic [31:0] result_transfer_count;
  logic prior_input_stall;
  logic prior_output_stall;
  logic signed [15:0] prior_s_i, prior_s_q;
  logic prior_s_last;
  logic signed [8:0] prior_peak_bin;
  logic signed [23:0] prior_frequency;
  logic signed [19:0] prior_velocity;
  logic [36:0] prior_power;
  logic [3:0] prior_status;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      // Skip the asynchronous time-zero edge; check from the first full reset cycle.
      if (checked_cycles === 32'd0)
        assert (!m_valid)
          else $fatal(1, "result_valid did not clear while reset was active");
      accepted_index <= 0;
      discarding <= 0;
      legal_frame_count <= 0;
      result_transfer_count <= 0;
      prior_input_stall <= 0;
      prior_output_stall <= 0;
      prior_s_i <= 0;
      prior_s_q <= 0;
      prior_s_last <= 0;
      prior_peak_bin <= 0;
      prior_frequency <= 0;
      prior_velocity <= 0;
      prior_power <= 0;
      prior_status <= 0;
      checked_cycles <= 0;
    end else begin
      checked_cycles <= checked_cycles + 1'b1;

      if (prior_input_stall) begin
        assert (s_valid && s_i == prior_s_i && s_q == prior_s_q &&
                s_last == prior_s_last)
          else $fatal(1, "source payload changed before input handshake");
      end
      if (prior_output_stall) begin
        assert (m_valid && m_peak_bin == prior_peak_bin &&
                m_frequency_q8_hz == prior_frequency &&
                m_velocity_q8_mm_s == prior_velocity &&
                m_peak_power == prior_power && m_status == prior_status)
          else $fatal(1, "result payload changed before output handshake");
      end

      prior_input_stall <= s_valid && !s_ready;
      if (s_valid && !s_ready) begin
        prior_s_i <= s_i;
        prior_s_q <= s_q;
        prior_s_last <= s_last;
      end
      prior_output_stall <= m_valid && !m_ready;
      if (m_valid && !m_ready) begin
        prior_peak_bin <= m_peak_bin;
        prior_frequency <= m_frequency_q8_hz;
        prior_velocity <= m_velocity_q8_mm_s;
        prior_power <= m_peak_power;
        prior_status <= m_status;
      end

      if (s_valid && s_ready) begin
        if (discarding) begin
          if (s_last) discarding <= 0;
        end else if (s_last) begin
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

      if (m_valid && m_ready) begin
        assert (result_transfer_count < legal_frame_count)
          else $fatal(1, "result transfer has no accepted legal frame");
        result_transfer_count <= result_transfer_count + 1'b1;
      end
    end
  end
endmodule

// Simulation-only shell: preserves the canonical core and its public port names.
module doppler_core_contract_top (
  input logic clk,
  input logic rst_n,
  input logic s_valid,
  output logic s_ready,
  input logic signed [15:0] s_i,
  input logic signed [15:0] s_q,
  input logic s_last,
  output logic m_valid,
  input logic m_ready,
  output logic signed [8:0] m_peak_bin,
  output logic signed [23:0] m_frequency_q8_hz,
  output logic signed [19:0] m_velocity_q8_mm_s,
  output logic [36:0] m_peak_power,
  output logic [3:0] m_status,
  output logic [31:0] assertion_checked_cycles
);
  doppler_core canonical_core (.*);
  doppler_stream_sva contract_checks (
    .clk, .rst_n, .s_valid, .s_ready, .s_i, .s_q, .s_last,
    .m_valid, .m_ready, .m_peak_bin, .m_frequency_q8_hz,
    .m_velocity_q8_mm_s, .m_peak_power, .m_status,
    .checked_cycles(assertion_checked_cycles)
  );
endmodule
