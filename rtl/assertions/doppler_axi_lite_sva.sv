// Icarus-compatible immediate assertions over the public AXI4-Lite interface.
module doppler_axi_lite_sva (
  input logic s_axi_aclk,
  input logic s_axi_aresetn,
  input logic [31:0] s_axi_awaddr,
  input logic s_axi_awvalid,
  input logic s_axi_awready,
  input logic [31:0] s_axi_wdata,
  input logic [3:0] s_axi_wstrb,
  input logic s_axi_wvalid,
  input logic s_axi_wready,
  input logic [1:0] s_axi_bresp,
  input logic s_axi_bvalid,
  input logic s_axi_bready,
  input logic [31:0] s_axi_araddr,
  input logic s_axi_arvalid,
  input logic s_axi_arready,
  input logic [31:0] s_axi_rdata,
  input logic [1:0] s_axi_rresp,
  input logic s_axi_rvalid,
  input logic s_axi_rready,
  output logic [31:0] assertion_checked_cycles
);
  logic prior_bstall, prior_rstall;
  logic [1:0] prior_bresp, prior_rresp;
  logic [31:0] prior_rdata;
  logic aw_outstanding, w_outstanding, read_outstanding;
  logic [31:0] accepted_aw, accepted_w, accepted_ar;
  logic [31:0] accepted_b, accepted_r;

  always_ff @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      prior_bstall <= 1'b0;
      prior_rstall <= 1'b0;
      prior_bresp <= 2'b0;
      prior_rresp <= 2'b0;
      prior_rdata <= 32'b0;
      aw_outstanding <= 1'b0;
      w_outstanding <= 1'b0;
      read_outstanding <= 1'b0;
      accepted_aw <= 32'b0;
      accepted_w <= 32'b0;
      accepted_ar <= 32'b0;
      accepted_b <= 32'b0;
      accepted_r <= 32'b0;
      assertion_checked_cycles <= 32'b0;
    end else begin
      assertion_checked_cycles <= assertion_checked_cycles + 1'b1;

      if (prior_bstall)
        assert (s_axi_bvalid && s_axi_bresp == prior_bresp)
          else $fatal(1, "AXI-Lite B response changed while stalled");
      if (prior_rstall)
        assert (s_axi_rvalid && s_axi_rdata == prior_rdata && s_axi_rresp == prior_rresp)
          else $fatal(1, "AXI-Lite R response changed while stalled");

      if (aw_outstanding) begin
        assert (!s_axi_awready)
          else $fatal(1, "pending AW address could be overwritten");
      end
      if (w_outstanding) begin
        assert (!s_axi_wready)
          else $fatal(1, "pending W payload could be overwritten");
      end
      if (read_outstanding)
        assert (!s_axi_arready)
          else $fatal(1, "pending read response could be overwritten");

      if (s_axi_awvalid && s_axi_awready) begin
        aw_outstanding <= 1'b1;
        accepted_aw <= accepted_aw + 1'b1;
      end
      if (s_axi_wvalid && s_axi_wready) begin
        w_outstanding <= 1'b1;
        accepted_w <= accepted_w + 1'b1;
      end
      if (s_axi_bvalid) begin
        assert (aw_outstanding && w_outstanding)
          else $fatal(1, "B response did not have both AW and W");
      end
      if (s_axi_bvalid && s_axi_bready) begin
        assert (accepted_b < accepted_aw && accepted_b < accepted_w)
          else $fatal(1, "duplicate AXI-Lite B response");
        accepted_b <= accepted_b + 1'b1;
        aw_outstanding <= 1'b0;
        w_outstanding <= 1'b0;
      end

      if (s_axi_arvalid && s_axi_arready) begin
        read_outstanding <= 1'b1;
        accepted_ar <= accepted_ar + 1'b1;
      end
      if (s_axi_rvalid && s_axi_rready) begin
        assert (read_outstanding && accepted_r < accepted_ar)
          else $fatal(1, "duplicate AXI-Lite R response");
        read_outstanding <= 1'b0;
        accepted_r <= accepted_r + 1'b1;
      end

      prior_bstall <= s_axi_bvalid && !s_axi_bready;
      if (s_axi_bvalid && !s_axi_bready)
        prior_bresp <= s_axi_bresp;
      prior_rstall <= s_axi_rvalid && !s_axi_rready;
      if (s_axi_rvalid && !s_axi_rready) begin
        prior_rdata <= s_axi_rdata;
        prior_rresp <= s_axi_rresp;
      end
    end
  end
endmodule

module doppler_axi_lite_contract_top (
  input logic s_axi_aclk,
  input logic s_axi_aresetn,
  input logic [31:0] s_axi_awaddr,
  input logic s_axi_awvalid,
  output logic s_axi_awready,
  input logic [31:0] s_axi_wdata,
  input logic [3:0] s_axi_wstrb,
  input logic s_axi_wvalid,
  output logic s_axi_wready,
  output logic [1:0] s_axi_bresp,
  output logic s_axi_bvalid,
  input logic s_axi_bready,
  input logic [31:0] s_axi_araddr,
  input logic s_axi_arvalid,
  output logic s_axi_arready,
  output logic [31:0] s_axi_rdata,
  output logic [1:0] s_axi_rresp,
  output logic s_axi_rvalid,
  input logic s_axi_rready,
  input logic stream_input_ready,
  input logic stream_output_valid,
  input logic [127:0] result_data,
  input logic result_valid,
  input logic result_ready,
  output logic enable,
  output logic soft_reset_pulse,
  output logic irq,
  output logic [31:0] assertion_checked_cycles
);
  doppler_axi_lite_regs regs (.*);
  doppler_axi_lite_sva checks (.*);
endmodule
