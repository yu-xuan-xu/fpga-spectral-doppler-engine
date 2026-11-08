module frame_checker_256 (
  input  logic clk,
  input  logic rst_n,
  input  logic s_valid,
  output logic s_ready,
  input  logic signed [15:0] s_i,
  input  logic signed [15:0] s_q,
  input  logic s_last,
  output logic m_valid,
  input  logic m_ready,
  output logic signed [15:0] m_i,
  output logic signed [15:0] m_q,
  output logic m_last,
  output logic frame_error_event
);
  typedef enum logic [2:0] {CAPTURE, DISCARD, REPLAY_SET, REPLAY_CAPTURE, REPLAY_SEND} state_t;
  state_t state;
  logic [7:0] capture_count, replay_count;
  logic ram_we;
  logic [7:0] ram_addr;
  logic signed [15:0] ram_i, ram_q;

  sync_ram_256x16 ram_frame_i(.clk, .we(ram_we), .addr(ram_addr), .wdata(s_i), .rdata(ram_i));
  sync_ram_256x16 ram_frame_q(.clk, .we(ram_we), .addr(ram_addr), .wdata(s_q), .rdata(ram_q));

  assign s_ready = (state == CAPTURE) || (state == DISCARD);
  assign m_valid = state == REPLAY_SEND;
  assign m_last = replay_count == 8'hff;
  assign ram_we = (state == CAPTURE) && s_valid;
  assign ram_addr = state == CAPTURE ? capture_count : replay_count;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state <= CAPTURE;
      capture_count <= 0;
      replay_count <= 0;
      m_i <= 0;
      m_q <= 0;
      frame_error_event <= 0;
    end else begin
      frame_error_event <= 0;
      case (state)
        CAPTURE: if (s_valid) begin
          if (s_last && capture_count != 8'hff) begin
            capture_count <= 0;
            frame_error_event <= 1;
          end else if (!s_last && capture_count == 8'hff) begin
            capture_count <= 0;
            frame_error_event <= 1;
            state <= DISCARD;
          end else if (s_last) begin
            capture_count <= 0;
            replay_count <= 0;
            state <= REPLAY_SET;
          end else capture_count <= capture_count + 1'b1;
        end
        DISCARD: if (s_valid && s_last) state <= CAPTURE;
        REPLAY_SET: state <= REPLAY_CAPTURE;
        REPLAY_CAPTURE: begin
          m_i <= ram_i;
          m_q <= ram_q;
          state <= REPLAY_SEND;
        end
        REPLAY_SEND: if (m_ready) begin
          if (replay_count == 8'hff) begin
            replay_count <= 0;
            state <= CAPTURE;
          end else begin
            replay_count <= replay_count + 1'b1;
            state <= REPLAY_SET;
          end
        end
        default: state <= CAPTURE;
      endcase
    end
  end
endmodule
