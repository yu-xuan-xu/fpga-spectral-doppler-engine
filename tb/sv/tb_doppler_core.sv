`timescale 1ns/1ps
module tb_doppler_core;
  logic clk=0,rst_n=0,s_valid=0,s_ready,s_last=0,m_valid,m_ready=1;
  logic signed [15:0] s_i=0,s_q=0; logic signed [8:0] peak_bin;
  logic signed [23:0] frequency; logic signed [19:0] velocity; logic [36:0] peak_power;
  logic [3:0] status; logic [31:0] samples[0:255];
  always #5 clk=~clk;
  doppler_core dut(.clk,.rst_n,.s_valid,.s_ready,.s_i,.s_q,.s_last,.m_valid,.m_ready,
    .m_peak_bin(peak_bin),.m_frequency_q8_hz(frequency),.m_velocity_q8_mm_s(velocity),
    .m_peak_power(peak_power),.m_status(status));
  initial begin
    $readmemh("tb/sv/fft_tone_bin16.mem",samples);
    repeat(3) @(posedge clk); rst_n<=1;
    for(int k=0;k<256;k++) begin
      while(!s_ready) @(posedge clk);
      s_valid<=1; s_i<=samples[k][31:16]; s_q<=samples[k][15:0]; s_last<=(k==255); @(posedge clk);
    end
    s_valid<=0;s_last<=0; wait(m_valid); #1;
    if(peak_bin!==9'sd16 || frequency!==24'sd320000 || velocity!==20'sd49280)
      $fatal(1,"core failed bin=%0d freq=%0d vel=%0d",peak_bin,frequency,velocity);
    $display("PASS Doppler core bin=%0d power=%0d status=%b",peak_bin,peak_power,status);
    $finish;
  end
endmodule
