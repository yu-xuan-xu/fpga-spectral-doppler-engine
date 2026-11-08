`timescale 1ns/1ps
module tb_fft_iterative;
  logic clk=0, rst_n=0, s_valid=0, s_ready, s_last=0, m_valid, m_ready=1;
  logic signed [15:0] s_re=0, s_im=0; logic signed [17:0] m_re,m_im;
  logic [7:0] m_bin; logic m_last,busy,frame_error;
  logic [31:0] samples [0:255]; integer peak_bin=0; integer received=0;
  longint peak_power=0; longint power;
  always #5 clk=~clk;
  fft_iterative_256 dut(.*);
  initial begin
    $readmemh("tb/sv/fft_tone_bin16.mem",samples);
    repeat(2) @(posedge clk); rst_n<=1;
    for(int k=0;k<256;k++) begin
      while(!s_ready) @(posedge clk);
      s_valid<=1; s_re<=samples[k][31:16]; s_im<=samples[k][15:0]; s_last<=(k==255);
      @(posedge clk);
    end
    s_valid<=0; s_last<=0;
    while(received<256) begin
      @(posedge clk);
      if(m_valid && m_ready) begin
        power=$signed(m_re)*$signed(m_re)+$signed(m_im)*$signed(m_im);
        if(power>peak_power) begin peak_power=power; peak_bin=m_bin; end
        received=received+1;
      end
    end
    if(frame_error || peak_bin!=16) $fatal(1,"FFT failed peak=%0d error=%0d",peak_bin,frame_error);
    $display("PASS iterative FFT peak=%0d power=%0d",peak_bin,peak_power);
    $finish;
  end
endmodule
