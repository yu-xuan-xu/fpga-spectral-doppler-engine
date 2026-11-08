module power_calculator (
  input logic clk, input logic rst_n,
  input logic s_valid, output logic s_ready,
  input logic signed [17:0] s_re, input logic signed [17:0] s_im,
  input logic [7:0] s_bin, input logic s_last,
  output logic m_valid, input logic m_ready,
  output logic [36:0] m_power, output logic [7:0] m_bin, output logic m_last
);
  typedef enum logic [1:0] {IDLE, SQUARE_RE, SQUARE_IM, RESULT} state_t;
  state_t state;
  logic [17:0] magnitude_re, magnitude_im, multiplier;
  logic [35:0] accumulator, re_square;
  logic [4:0] bit_index;
  logic [7:0] saved_bin;
  logic saved_last;

  function automatic logic [17:0] magnitude(input logic signed [17:0] value);
    magnitude = value[17] ? $unsigned(-value) : $unsigned(value);
  endfunction

  assign s_ready = state == IDLE;
  assign m_valid = state == RESULT;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state <= IDLE; magnitude_re <= 0; magnitude_im <= 0; multiplier <= 0;
      accumulator <= 0; re_square <= 0; bit_index <= 0; saved_bin <= 0;
      saved_last <= 0; m_power <= 0; m_bin <= 0; m_last <= 0;
    end else case (state)
      IDLE: if (s_valid) begin
        magnitude_re <= magnitude(s_re); magnitude_im <= magnitude(s_im);
        multiplier <= magnitude(s_re); accumulator <= 0; bit_index <= 0;
        saved_bin <= s_bin; saved_last <= s_last; state <= SQUARE_RE;
      end
      SQUARE_RE: begin
        if (magnitude_re[bit_index]) accumulator <= accumulator + (multiplier << bit_index);
        if (bit_index == 5'd17) begin
          re_square <= accumulator +
            (magnitude_re[bit_index] ? (multiplier << bit_index) : 36'd0);
          multiplier <= magnitude_im; accumulator <= 0; bit_index <= 0; state <= SQUARE_IM;
        end else bit_index <= bit_index + 1'b1;
      end
      SQUARE_IM: begin
        if (magnitude_im[bit_index]) accumulator <= accumulator + (multiplier << bit_index);
        if (bit_index == 5'd17) begin
          m_power <= {1'b0,re_square} + {1'b0,accumulator} +
            (magnitude_im[bit_index] ? {1'b0,(multiplier << bit_index)} : 37'd0);
          m_bin <= saved_bin; m_last <= saved_last; state <= RESULT;
        end else bit_index <= bit_index + 1'b1;
      end
      RESULT: if (m_ready) state <= IDLE;
      default: state <= IDLE;
    endcase
  end
endmodule
