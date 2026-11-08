module doppler_core (
  input logic clk, input logic rst_n,
  input logic s_valid, output logic s_ready,
  input logic signed [15:0] s_i, input logic signed [15:0] s_q, input logic s_last,
  output logic m_valid, input logic m_ready,
  output logic signed [8:0] m_peak_bin,
  output logic signed [23:0] m_frequency_q8_hz,
  output logic signed [19:0] m_velocity_q8_mm_s,
  output logic [36:0] m_peak_power,
  output logic [3:0] m_status
);
  logic c_valid,c_ready,c_last,c_error; logic signed [15:0] c_i,c_q;
  logic f_valid,f_ready,f_last,f_overflow; logic signed [17:0] f_i,f_q;
  logic w_valid,w_ready,w_last; logic signed [15:0] w_i,w_q;
  logic x_valid,x_ready,x_last,x_busy,x_error; logic signed [17:0] x_re,x_im; logic [7:0] x_bin;
  logic p_valid,p_ready,p_last; logic [36:0] power; logic [7:0] p_bin;
  logic k_valid,k_ready,k_low_confidence; logic signed [8:0] peak_bin; logic [36:0] peak_power;
  logic overflow_sticky, frame_error_sticky;
  logic [3:0] result_status;
  frame_checker_256 frame_guard(.clk,.rst_n,.s_valid,.s_ready,.s_i,.s_q,.s_last,
    .m_valid(c_valid),.m_ready(c_ready),.m_i(c_i),.m_q(c_q),.m_last(c_last),
    .frame_error_event(c_error));
  dc_wall_filter filter(.clk,.rst_n,.s_valid(c_valid),.s_ready(c_ready),.s_i(c_i),.s_q(c_q),.s_last(c_last),
    .m_valid(f_valid),.m_ready(f_ready),.m_i(f_i),.m_q(f_q),.m_last(f_last),.overflow(f_overflow));
  window_multiplier window(.clk,.rst_n,.s_valid(f_valid),.s_ready(f_ready),.s_i(f_i),.s_q(f_q),
    .s_last(f_last),.m_valid(w_valid),.m_ready(w_ready),.m_i(w_i),.m_q(w_q),.m_last(w_last));
  fft_iterative_256 fft(.clk,.rst_n,.s_valid(w_valid),.s_ready(w_ready),.s_re(w_i),.s_im(w_q),
    .s_last(w_last),.m_valid(x_valid),.m_ready(x_ready),.m_re(x_re),.m_im(x_im),.m_bin(x_bin),
    .m_last(x_last),.busy(x_busy),.frame_error(x_error));
  power_calculator pwr(.clk,.rst_n,.s_valid(x_valid),.s_ready(x_ready),.s_re(x_re),.s_im(x_im),
    .s_bin(x_bin),.s_last(x_last),.m_valid(p_valid),.m_ready(p_ready),.m_power(power),.m_bin(p_bin),.m_last(p_last));
  peak_bin_detector peak(.clk,.rst_n,.s_valid(p_valid),.s_ready(p_ready),.s_power(power),.s_bin(p_bin),
    .s_last(p_last),.m_valid(k_valid),.m_ready(k_ready),.m_peak_bin(peak_bin),.m_peak_power(peak_power),
    .m_low_confidence(k_low_confidence));
  assign result_status = {1'b0, overflow_sticky, k_low_confidence,
                          frame_error_sticky | x_error};
  velocity_mapper mapper(.clk,.rst_n,.s_valid(k_valid),.s_ready(k_ready),.s_peak_bin(peak_bin),
    .s_peak_power(peak_power),.s_status(result_status),.m_valid,.m_ready,.m_frequency_q8_hz,
    .m_velocity_q8_mm_s,.m_peak_bin,.m_peak_power,.m_status);

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      overflow_sticky <= 0;
      frame_error_sticky <= 0;
    end else begin
      if (c_error) frame_error_sticky <= 1;
      if (f_valid && f_ready && f_overflow) overflow_sticky <= 1;
      if (m_valid && m_ready) begin
        overflow_sticky <= 0;
        frame_error_sticky <= 0;
      end
    end
  end
endmodule
