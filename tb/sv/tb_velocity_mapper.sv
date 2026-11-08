`timescale 1ns/1ps
module tb_velocity_mapper;
  logic clk=0,rst_n=0,s_valid=0,s_ready,m_valid,m_ready=1;
  logic signed [8:0] s_peak_bin;
  logic [36:0] s_peak_power=37'd123;
  logic [3:0] s_status=4'b0110;
  logic signed [23:0] frequency;
  logic signed [19:0] velocity;
  logic signed [8:0] out_bin;
  logic [36:0] out_power;
  logic [3:0] out_status;
  always #5 clk=~clk;
  velocity_mapper dut(.clk,.rst_n,.s_valid,.s_ready,.s_peak_bin,.s_peak_power,.s_status,
    .m_valid,.m_ready,.m_frequency_q8_hz(frequency),.m_velocity_q8_mm_s(velocity),
    .m_peak_bin(out_bin),.m_peak_power(out_power),.m_status(out_status));
  initial begin
    repeat(2) @(posedge clk); rst_n<=1;
    for(integer k=-128;k<=127;k=k+1) begin
      while(!s_ready) @(posedge clk);
      s_valid<=1; s_peak_bin<=k; @(posedge clk); s_valid<=0;
      wait(m_valid); #1;
      if(out_bin!==k || $signed(frequency)!==k*20000 || $signed(velocity)!==k*3080 ||
         out_power!==37'd123 || out_status!==4'b0110)
        $fatal(1,"mapper mismatch bin=%0d freq=%0d velocity=%0d",k,$signed(frequency),$signed(velocity));
      @(posedge clk);
    end
    $display("PASS velocity mapper all signed bins");
    $finish;
  end
endmodule
