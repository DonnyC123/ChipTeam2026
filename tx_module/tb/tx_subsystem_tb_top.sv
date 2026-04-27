module tx_subsystem_tb_top #(
    parameter int FIFO_DEPTH = 16,
    parameter int DESC_DEPTH = 16
);

  logic        clk;
  logic        dma_aclk;
  logic        dma_aresetn;
  logic [255:0] s_axis_dma_tdata_i;
  logic [31:0] s_axis_dma_tkeep_i;
  logic        s_axis_dma_tvalid_i;
  logic        s_axis_dma_tlast_i;
  logic        s_axis_dma_tready_o;

  logic        tx_aclk;
  logic        tx_aresetn;
  logic [63:0] m_axis_pcs_tdata_o;
  logic [7:0]  m_axis_pcs_tkeep_o;
  logic        m_axis_pcs_tvalid_o;
  logic        m_axis_pcs_tlast_o;
  logic        m_axis_pcs_tready_i;

  assign clk = tx_aclk;

  tx_subsystem_axis_1q #(
      .FIFO_DEPTH(FIFO_DEPTH),
      .DESC_DEPTH(DESC_DEPTH)
  ) dut (
      .dma_aclk             (dma_aclk),
      .dma_aresetn          (dma_aresetn),
      .s_axis_dma_tdata_i   (s_axis_dma_tdata_i),
      .s_axis_dma_tkeep_i   (s_axis_dma_tkeep_i),
      .s_axis_dma_tvalid_i  (s_axis_dma_tvalid_i),
      .s_axis_dma_tlast_i   (s_axis_dma_tlast_i),
      .s_axis_dma_tready_o  (s_axis_dma_tready_o),
      .tx_aclk              (tx_aclk),
      .tx_aresetn           (tx_aresetn),
      .m_axis_pcs_tdata_o   (m_axis_pcs_tdata_o),
      .m_axis_pcs_tkeep_o   (m_axis_pcs_tkeep_o),
      .m_axis_pcs_tvalid_o  (m_axis_pcs_tvalid_o),
      .m_axis_pcs_tlast_o   (m_axis_pcs_tlast_o),
      .m_axis_pcs_tready_i  (m_axis_pcs_tready_i)
  );

endmodule
