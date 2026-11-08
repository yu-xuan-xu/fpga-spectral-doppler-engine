`timescale 1ns/1ps
module tb_post_fft;
  logic clk=0, rst_n=0, valid=0, ready, last=0;
  logic signed [17:0] re=0, im=0;
  logic [7:0] bin=0;
  logic p_valid, p_ready, p_last; logic [36:0] power; logic [7:0] p_bin;
  logic peak_valid, peak_ready; logic signed [8:0] peak_bin; logic [36:0] peak_power;
  logic low_confidence;
  logic out_valid; logic signed [23:0] frequency; logic signed [19:0] velocity;
  logic signed [8:0] out_bin; logic [36:0] out_power;
  always #5 clk=~clk;
  power_calculator pwr(.*,.s_valid(valid),.s_ready(ready),.s_re(re),.s_im(im),.s_bin(bin),
    .s_last(last),.m_valid(p_valid),.m_ready(p_ready),.m_power(power),.m_bin(p_bin),.m_last(p_last));
  peak_bin_detector peak(.clk,.rst_n,.s_valid(p_valid),.s_ready(p_ready),.s_power(power),
    .s_bin(p_bin),.s_last(p_last),.m_valid(peak_valid),.m_ready(peak_ready),.m_peak_bin(peak_bin),
    .m_peak_power(peak_power),.m_low_confidence(low_confidence));
  velocity_mapper map(.clk,.rst_n,.s_valid(peak_valid),.s_ready(peak_ready),.s_peak_bin(peak_bin),
    .s_peak_power(peak_power),.s_status({2'b0,low_confidence,1'b0}),.m_valid(out_valid),
    .m_ready(1'b1),.m_frequency_q8_hz(frequency),.m_velocity_q8_mm_s(velocity),
    .m_peak_bin(out_bin),.m_peak_power(out_power),.m_status());
  initial begin
    repeat(2) @(posedge clk); rst_n<=1; @(posedge clk);
    for (int k=0;k<256;k++) begin
      while(!ready) @(posedge clk);
      valid<=1; bin<=k; last<=(k==255);
      if(k==16) begin re<=18'sd1000; im<=18'sd2000; end
      else begin re<=18'sd1; im<=18'sd1; end
      @(posedge clk);
    end
    valid<=0; last<=0;
    wait(out_valid); #1;
    if(out_bin!==9'sd16 || frequency!==24'sd320000 || velocity!==20'sd49280)
      $fatal(1,"bad result bin=%0d freq=%0d vel=%0d",out_bin,frequency,velocity);
    $display("PASS post-FFT path bin=%0d power=%0d",out_bin,out_power);
    $finish;
  end
endmodule
