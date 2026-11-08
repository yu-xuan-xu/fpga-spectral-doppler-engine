package doppler_pkg;
  parameter int FFT_SIZE = 256;
  parameter int SAMPLE_W = 16;
  parameter int INTERNAL_W = 18;

  function automatic logic signed [INTERNAL_W-1:0] sat18(input logic signed [20:0] value);
    if (value > 21'sd131071) sat18 = 18'sd131071;
    else if (value < -21'sd131072) sat18 = -18'sd131072;
    else sat18 = value[INTERNAL_W-1:0];
  endfunction

  function automatic logic signed [8:0] signed_bin(input logic [7:0] raw_bin);
    signed_bin = raw_bin[7] ? $signed({1'b1, raw_bin}) : $signed({1'b0, raw_bin});
  endfunction
endpackage
