module doppler_axi_controlled_top (
  input  logic         aclk,
  input  logic         aresetn,

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

  input  logic [31:0]  s_axis_tdata,
  input  logic         s_axis_tvalid,
  output logic         s_axis_tready,
  input  logic         s_axis_tlast,
  output logic [127:0] m_axis_tdata,
  output logic         m_axis_tvalid,
  input  logic         m_axis_tready,
  output logic         m_axis_tlast,
  output logic         irq
);
  logic enable;
  logic soft_reset_pulse;
  logic datapath_aresetn;
  logic wrapper_s_axis_tready;
  logic wrapper_m_axis_tvalid;
  logic wrapper_m_axis_tready;

  assign datapath_aresetn = aresetn && !soft_reset_pulse;
  assign s_axis_tready = enable && datapath_aresetn && wrapper_s_axis_tready;
  assign m_axis_tvalid = datapath_aresetn && wrapper_m_axis_tvalid;
  assign wrapper_m_axis_tready = datapath_aresetn && m_axis_tready;

  doppler_axi_lite_regs control_regs (
    .s_axi_aclk(aclk),
    .s_axi_aresetn(aresetn),
    .stream_input_ready(s_axis_tready),
    .stream_output_valid(m_axis_tvalid),
    .result_data(m_axis_tdata),
    .result_valid(m_axis_tvalid),
    .result_ready(m_axis_tready),
    .enable(enable),
    .soft_reset_pulse(soft_reset_pulse),
    .irq(irq),
    .*
  );

  doppler_axi_stream_wrapper stream_wrapper (
    .aclk(aclk),
    .aresetn(datapath_aresetn),
    .s_axis_tdata(s_axis_tdata),
    .s_axis_tvalid(s_axis_tvalid && enable && datapath_aresetn),
    .s_axis_tready(wrapper_s_axis_tready),
    .s_axis_tlast(s_axis_tlast),
    .m_axis_tdata(m_axis_tdata),
    .m_axis_tvalid(wrapper_m_axis_tvalid),
    .m_axis_tready(wrapper_m_axis_tready),
    .m_axis_tlast(m_axis_tlast)
  );
endmodule
