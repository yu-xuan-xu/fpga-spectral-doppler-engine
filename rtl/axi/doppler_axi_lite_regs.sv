module doppler_axi_lite_regs (
  input  logic         s_axi_aclk,
  input  logic         s_axi_aresetn,

  input  logic [31:0]  s_axi_awaddr,
  input  logic         s_axi_awvalid,
  output logic         s_axi_awready,
  input  logic [31:0]  s_axi_wdata,
  input  logic [3:0]   s_axi_wstrb,
  input  logic         s_axi_wvalid,
  output logic         s_axi_wready,
  output logic [1:0]   s_axi_bresp,
  output logic         s_axi_bvalid,
  input  logic         s_axi_bready,

  input  logic [31:0]  s_axi_araddr,
  input  logic         s_axi_arvalid,
  output logic         s_axi_arready,
  output logic [31:0]  s_axi_rdata,
  output logic [1:0]   s_axi_rresp,
  output logic         s_axi_rvalid,
  input  logic         s_axi_rready,

  input  logic         stream_input_ready,
  input  logic         stream_output_valid,
  input  logic [127:0] result_data,
  input  logic         result_valid,
  input  logic         result_ready,

  output logic         enable,
  output logic         soft_reset_pulse,
  output logic         irq
);
  localparam logic [1:0] RESP_OKAY = 2'b00;
  localparam logic [1:0] RESP_SLVERR = 2'b10;
  localparam logic [31:0] VERSION = 32'h0200_0000;
  localparam logic [31:0] CAPABILITIES = 32'h0310_4100;

  logic aw_pending;
  logic [31:0] saved_awaddr;
  logic w_pending;
  logic [31:0] saved_wdata;
  logic [3:0] saved_wstrb;

  logic [31:0] result_count;
  logic [31:0] last_sequence;
  logic signed [8:0] last_peak_bin;
  logic signed [23:0] last_frequency;
  logic signed [19:0] last_velocity;
  logic [36:0] last_power;
  logic [3:0] last_status;
  logic last_result_valid;
  logic irq_enable;
  logic irq_status;
  logic [31:0] scratch;

  wire write_execute = aw_pending && w_pending && !s_axi_bvalid;
  wire soft_reset_write = write_execute && (saved_awaddr == 32'h0000_0008) &&
                          saved_wstrb[0] && saved_wdata[1];
  wire result_transfer = result_valid && result_ready;

  assign s_axi_awready = s_axi_aresetn && !aw_pending && !s_axi_bvalid;
  assign s_axi_wready = s_axi_aresetn && !w_pending && !s_axi_bvalid;
  assign s_axi_arready = s_axi_aresetn && !s_axi_rvalid;
  assign irq = irq_enable && irq_status;

  function automatic logic [31:0] apply_wstrb(
    input logic [31:0] prior,
    input logic [31:0] next_value,
    input logic [3:0] strobes
  );
    integer byte_index;
    begin
      apply_wstrb = prior;
      for (byte_index = 0; byte_index < 4; byte_index = byte_index + 1)
        if (strobes[byte_index])
          apply_wstrb[byte_index * 8 +: 8] = next_value[byte_index * 8 +: 8];
    end
  endfunction

  function automatic logic write_address_valid(input logic [31:0] address);
    begin
      case (address)
        32'h0000_0008,
        32'h0000_0030,
        32'h0000_0034,
        32'h0000_0038: write_address_valid = 1'b1;
        default: write_address_valid = 1'b0;
      endcase
    end
  endfunction

  function automatic logic read_address_valid(input logic [31:0] address);
    begin
      case (address)
        32'h0000_0000, 32'h0000_0004, 32'h0000_0008, 32'h0000_000c,
        32'h0000_0010, 32'h0000_0014, 32'h0000_0018, 32'h0000_001c,
        32'h0000_0020, 32'h0000_0024, 32'h0000_0028, 32'h0000_002c,
        32'h0000_0030, 32'h0000_0034, 32'h0000_0038:
          read_address_valid = 1'b1;
        default: read_address_valid = 1'b0;
      endcase
    end
  endfunction

  always_ff @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      aw_pending <= 1'b0;
      saved_awaddr <= 32'b0;
      w_pending <= 1'b0;
      saved_wdata <= 32'b0;
      saved_wstrb <= 4'b0;
      s_axi_bresp <= RESP_OKAY;
      s_axi_bvalid <= 1'b0;
    end else begin
      if (s_axi_bvalid && s_axi_bready)
        s_axi_bvalid <= 1'b0;
      if (s_axi_awvalid && s_axi_awready) begin
        aw_pending <= 1'b1;
        saved_awaddr <= s_axi_awaddr;
      end
      if (s_axi_wvalid && s_axi_wready) begin
        w_pending <= 1'b1;
        saved_wdata <= s_axi_wdata;
        saved_wstrb <= s_axi_wstrb;
      end
      if (write_execute) begin
        aw_pending <= 1'b0;
        w_pending <= 1'b0;
        s_axi_bresp <= write_address_valid(saved_awaddr) ? RESP_OKAY : RESP_SLVERR;
        s_axi_bvalid <= 1'b1;
      end
    end
  end

  always_ff @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      s_axi_rdata <= 32'b0;
      s_axi_rresp <= RESP_OKAY;
      s_axi_rvalid <= 1'b0;
    end else begin
      if (s_axi_rvalid && s_axi_rready)
        s_axi_rvalid <= 1'b0;
      if (s_axi_arvalid && s_axi_arready) begin
        s_axi_rvalid <= 1'b1;
        s_axi_rresp <= read_address_valid(s_axi_araddr) ? RESP_OKAY : RESP_SLVERR;
        case (s_axi_araddr)
          32'h0000_0000: s_axi_rdata <= VERSION;
          32'h0000_0004: s_axi_rdata <= CAPABILITIES;
          32'h0000_0008: s_axi_rdata <= {31'b0, enable};
          32'h0000_000c: s_axi_rdata <= {
            27'b0, last_result_valid, irq_status, stream_output_valid,
            stream_input_ready, enable
          };
          32'h0000_0010: s_axi_rdata <= result_count;
          32'h0000_0014: s_axi_rdata <= last_sequence;
          32'h0000_0018: s_axi_rdata <= {{23{last_peak_bin[8]}}, last_peak_bin};
          32'h0000_001c: s_axi_rdata <= {{8{last_frequency[23]}}, last_frequency};
          32'h0000_0020: s_axi_rdata <= {{12{last_velocity[19]}}, last_velocity};
          32'h0000_0024: s_axi_rdata <= last_power[31:0];
          32'h0000_0028: s_axi_rdata <= {27'b0, last_power[36:32]};
          32'h0000_002c: s_axi_rdata <= {28'b0, last_status};
          32'h0000_0030: s_axi_rdata <= {31'b0, irq_enable};
          32'h0000_0034: s_axi_rdata <= {31'b0, irq_status};
          32'h0000_0038: s_axi_rdata <= scratch;
          default: s_axi_rdata <= 32'b0;
        endcase
      end
    end
  end

  always_ff @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      enable <= 1'b0;
      soft_reset_pulse <= 1'b0;
      result_count <= 32'b0;
      last_sequence <= 32'b0;
      last_peak_bin <= '0;
      last_frequency <= '0;
      last_velocity <= '0;
      last_power <= '0;
      last_status <= '0;
      last_result_valid <= 1'b0;
      irq_enable <= 1'b0;
      irq_status <= 1'b0;
      scratch <= 32'b0;
    end else begin
      soft_reset_pulse <= 1'b0;

      if (soft_reset_write) begin
        enable <= 1'b0;
        soft_reset_pulse <= 1'b1;
        result_count <= 32'b0;
        last_sequence <= 32'b0;
        last_peak_bin <= '0;
        last_frequency <= '0;
        last_velocity <= '0;
        last_power <= '0;
        last_status <= '0;
        last_result_valid <= 1'b0;
        irq_status <= 1'b0;
      end else begin
        if (write_execute && write_address_valid(saved_awaddr)) begin
          case (saved_awaddr)
            32'h0000_0008:
              if (saved_wstrb[0])
                enable <= saved_wdata[0];
            32'h0000_0030:
              if (saved_wstrb[0])
                irq_enable <= saved_wdata[0];
            32'h0000_0034:
              if (saved_wstrb[0] && saved_wdata[0])
                irq_status <= 1'b0;
            32'h0000_0038:
              scratch <= apply_wstrb(scratch, saved_wdata, saved_wstrb);
            default: begin end
          endcase
        end

        if (result_transfer) begin
          result_count <= result_count + 1'b1;
          last_sequence <= result_data[31:0];
          last_peak_bin <= result_data[40:32];
          last_frequency <= result_data[64:41];
          last_velocity <= result_data[84:65];
          last_power <= result_data[121:85];
          last_status <= result_data[125:122];
          last_result_valid <= 1'b1;
          irq_status <= 1'b1;
        end
      end
    end
  end
endmodule
