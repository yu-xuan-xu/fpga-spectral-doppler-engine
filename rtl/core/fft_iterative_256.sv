module fft_iterative_256 (
  input  logic clk,
  input  logic rst_n,
  input  logic s_valid,
  output logic s_ready,
  input  logic signed [15:0] s_re,
  input  logic signed [15:0] s_im,
  input  logic s_last,
  output logic m_valid,
  input  logic m_ready,
  output logic signed [17:0] m_re,
  output logic signed [17:0] m_im,
  output logic [7:0] m_bin,
  output logic m_last,
  output logic busy,
  output logic frame_error
);
  typedef enum logic [3:0] {
    LOAD, SET_A, CAP_A, CAP_B, WRITE_A, WRITE_B, OUTPUT_SET, OUTPUT_CAPTURE,
    OUTPUT_SEND
  } state_t;
  state_t state;
  logic [7:0] load_count, butterfly_count, output_count;
  logic [2:0] stage;
  logic [7:0] upper_address, lower_address;
  logic [6:0] twiddle_address;
  logic signed [15:0] a_re, a_im, b_re, b_im;
  logic signed [31:0] product_rr, product_ii, product_ri, product_ir;
  logic signed [32:0] product_re_wide, product_im_wide;
  logic signed [17:0] product_re, product_im;
  logic signed [17:0] sum_re, sum_im, diff_re, diff_im;
  logic signed [15:0] next_a_re, next_a_im, next_b_re, next_b_im;
  logic signed [15:0] output_re, output_im;
  logic [7:0] output_bin;
  logic ram_we;
  logic [7:0] ram_addr;
  logic signed [15:0] ram_wdata_re, ram_wdata_im, ram_rdata_re, ram_rdata_im;

`include "fft_twiddle_q15.svh"

  function automatic logic [7:0] bit_reverse(input logic [7:0] value);
    for (int bit_index = 0; bit_index < 8; bit_index++)
      bit_reverse[bit_index] = value[7-bit_index];
  endfunction

  function automatic logic signed [17:0] round_q15(input logic signed [32:0] value);
    logic signed [32:0] magnitude;
    begin
      magnitude = value < 0 ? -value : value;
      round_q15 = value < 0 ? -((magnitude + 33'sd16384) >>> 15) :
                              ((magnitude + 33'sd16384) >>> 15);
    end
  endfunction

  function automatic logic signed [15:0] scale_half(input logic signed [17:0] value);
    logic signed [17:0] magnitude;
    begin
      magnitude = value < 0 ? -value : value;
      scale_half = value < 0 ? -((magnitude + 18'sd1) >>> 1) :
                               ((magnitude + 18'sd1) >>> 1);
    end
  endfunction

  always_comb begin
    logic [7:0] half_span;
    logic [7:0] offset;
    half_span = 8'd1 << stage;
    offset = butterfly_count & (half_span - 1'b1);
    upper_address = ((butterfly_count >> stage) << (stage + 1'b1)) + offset;
    lower_address = upper_address + half_span;
    twiddle_address = offset << (7-stage);
    product_rr = b_re * twiddle_re(twiddle_address);
    product_ii = b_im * twiddle_im(twiddle_address);
    product_ri = b_re * twiddle_im(twiddle_address);
    product_ir = b_im * twiddle_re(twiddle_address);
    product_re_wide = $signed(product_rr) - $signed(product_ii);
    product_im_wide = $signed(product_ri) + $signed(product_ir);
    product_re = round_q15(product_re_wide);
    product_im = round_q15(product_im_wide);
    sum_re = $signed(a_re) + product_re;
    sum_im = $signed(a_im) + product_im;
    diff_re = $signed(a_re) - product_re;
    diff_im = $signed(a_im) - product_im;
    next_a_re = scale_half(sum_re);
    next_a_im = scale_half(sum_im);
    next_b_re = scale_half(diff_re);
    next_b_im = scale_half(diff_im);
  end

  assign s_ready = state == LOAD;
  assign busy = state != LOAD;
  assign m_valid = state == OUTPUT_SEND;
  assign m_re = {{2{output_re[15]}}, output_re};
  assign m_im = {{2{output_im[15]}}, output_im};
  assign m_bin = output_bin;
  assign m_last = output_bin == 8'hff;

  sync_ram_256x16 ram_re(
    .clk, .we(ram_we), .addr(ram_addr), .wdata(ram_wdata_re), .rdata(ram_rdata_re)
  );
  sync_ram_256x16 ram_im(
    .clk, .we(ram_we), .addr(ram_addr), .wdata(ram_wdata_im), .rdata(ram_rdata_im)
  );

  always_comb begin
    ram_we = 1'b0;
    ram_addr = upper_address;
    ram_wdata_re = '0;
    ram_wdata_im = '0;
    case (state)
      LOAD: begin
        ram_we = s_valid;
        ram_addr = bit_reverse(load_count);
        ram_wdata_re = s_re;
        ram_wdata_im = s_im;
      end
      CAP_A: ram_addr = lower_address;
      WRITE_A: begin
        ram_we = 1'b1; ram_addr = upper_address;
        ram_wdata_re = next_a_re; ram_wdata_im = next_a_im;
      end
      WRITE_B: begin
        ram_we = 1'b1; ram_addr = lower_address;
        ram_wdata_re = next_b_re; ram_wdata_im = next_b_im;
      end
      OUTPUT_SET: ram_addr = output_count;
      default: begin end
    endcase
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state <= LOAD; load_count <= 0; butterfly_count <= 0; output_count <= 0;
      stage <= 0; frame_error <= 0; a_re <= 0; a_im <= 0; b_re <= 0; b_im <= 0;
      output_re <= 0; output_im <= 0; output_bin <= 0;
    end else begin
      case (state)
        LOAD: if (s_valid) begin
          if (s_last != (load_count == 8'hff)) frame_error <= 1;
          if (load_count == 8'hff) begin
            load_count <= 0; stage <= 0; butterfly_count <= 0; state <= SET_A;
          end else load_count <= load_count + 1'b1;
        end
        SET_A: state <= CAP_A;
        CAP_A: begin a_re <= ram_rdata_re; a_im <= ram_rdata_im; state <= CAP_B; end
        CAP_B: begin b_re <= ram_rdata_re; b_im <= ram_rdata_im; state <= WRITE_A; end
        WRITE_A: state <= WRITE_B;
        WRITE_B: begin
          if (butterfly_count == 8'd127) begin
            butterfly_count <= 0;
            if (stage == 3'd7) begin output_count <= 0; state <= OUTPUT_SET; end
            else begin stage <= stage + 1'b1; state <= SET_A; end
          end else begin butterfly_count <= butterfly_count + 1'b1; state <= SET_A; end
        end
        OUTPUT_SET: state <= OUTPUT_CAPTURE;
        OUTPUT_CAPTURE: begin
          output_re <= ram_rdata_re; output_im <= ram_rdata_im;
          output_bin <= output_count; state <= OUTPUT_SEND;
        end
        OUTPUT_SEND: if (m_ready) begin
          if (output_bin == 8'hff) begin
            output_count <= 0; frame_error <= 0; state <= LOAD;
          end else begin output_count <= output_count + 1'b1; state <= OUTPUT_SET; end
        end
        default: state <= LOAD;
      endcase
    end
  end
endmodule
