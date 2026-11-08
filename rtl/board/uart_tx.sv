module uart_tx #(
  parameter integer CLOCK_HZ = 12000000,
  parameter integer BAUD = 115200,
  parameter integer DIVISOR = CLOCK_HZ / BAUD
) (
  input logic clk, input logic rst_n,
  input logic s_valid, output logic s_ready, input logic [7:0] s_data,
  output logic tx, output logic busy
);
  logic [9:0] shift;
  logic [3:0] bit_count;
  logic [$clog2(DIVISOR)-1:0] baud_count;
  assign s_ready = !busy;
  assign tx = busy ? shift[0] : 1'b1;
  always_ff @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin busy<=0; shift<=10'h3ff; bit_count<=0; baud_count<=0; end
    else if(s_valid && s_ready) begin
      shift<={1'b1,s_data,1'b0}; busy<=1; bit_count<=0; baud_count<=0;
    end else if(busy) begin
      if(baud_count==DIVISOR-1) begin
        baud_count<=0; shift<={1'b1,shift[9:1]};
        if(bit_count==9) begin busy<=0; bit_count<=0; end
        else bit_count<=bit_count+1'b1;
      end else baud_count<=baud_count+1'b1;
    end
  end
endmodule
