module crc16_ccitt (
  input logic [15:0] crc_in,
  input logic [7:0] data,
  output logic [15:0] crc_out
);
  always_comb begin
    crc_out = crc_in;
    for (integer bit_index=0; bit_index<8; bit_index=bit_index+1) begin
      if (crc_out[15] ^ data[7-bit_index])
        crc_out = {crc_out[14:0],1'b0} ^ 16'h1021;
      else crc_out = {crc_out[14:0],1'b0};
    end
  end
endmodule
