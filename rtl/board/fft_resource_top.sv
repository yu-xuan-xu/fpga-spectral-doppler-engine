module fft_resource_top(output logic signature);
  logic clk; logic rst_n=0; logic [5:0] reset_count=0; logic [7:0] sample_count=0;
  logic s_ready,m_valid,m_last,busy,frame_error; logic signed [17:0] m_re,m_im;
  logic [7:0] m_bin;
  SB_HFOSC #(.CLKHF_DIV("0b10")) oscillator (.CLKHFPU(1'b1),.CLKHFEN(1'b1),.CLKHF(clk));
  always_ff @(posedge clk) begin reset_count<=reset_count+!reset_count[5]; rst_n<=reset_count[5];
    if(rst_n && s_ready) sample_count<=sample_count+1'b1; end
  fft_iterative_256 fft(.clk,.rst_n,.s_valid(rst_n),.s_ready,
    .s_re({1'b0,sample_count,7'b0}),.s_im('0),.s_last(sample_count==8'hff),
    .m_valid,.m_ready(1'b1),.m_re,.m_im,.m_bin,.m_last,.busy,.frame_error);
  assign signature = ^{m_re,m_im,m_bin,m_valid,m_last,busy,frame_error};
endmodule
