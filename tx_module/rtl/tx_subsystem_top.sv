module tx_subsystem_top #(
    parameter int FIFO_DEPTH = 64,
    parameter int DESC_DEPTH = 32
) (
    input  logic        dma_aclk,
    input  logic        dma_aresetn,
    input  logic [255:0] s_axis_dma_tdata_i,
    input  logic [31:0] s_axis_dma_tkeep_i,
    input  logic        s_axis_dma_tvalid_i,
    input  logic        s_axis_dma_tlast_i,
    output logic        s_axis_dma_tready_o,

    input  logic        tx_aclk,
    input  logic        tx_aresetn,
    output logic [63:0] m_axis_pcs_tdata_o,
    output logic [7:0]  m_axis_pcs_tkeep_o,
    output logic        m_axis_pcs_tvalid_o,
    output logic        m_axis_pcs_tlast_o,
    input  logic        m_axis_pcs_tready_i
);

  logic [1:0] dma_rst_sync_q;
  logic [1:0] tx_rst_sync_q;
  logic       dma_rst;
  logic       tx_rst;

  always_ff @(posedge dma_aclk or negedge dma_aresetn) begin
    if (!dma_aresetn) begin
      dma_rst_sync_q <= 2'b11;
    end else begin
      dma_rst_sync_q <= {dma_rst_sync_q[0], 1'b0};
    end
  end

  always_ff @(posedge tx_aclk or negedge tx_aresetn) begin
    if (!tx_aresetn) begin
      tx_rst_sync_q <= 2'b11;
    end else begin
      tx_rst_sync_q <= {tx_rst_sync_q[0], 1'b0};
    end
  end

  assign dma_rst = dma_rst_sync_q[1];
  assign tx_rst  = tx_rst_sync_q[1];

  tx_subsystem #(
      .FIFO_DEPTH(FIFO_DEPTH),
      .DESC_DEPTH(DESC_DEPTH)
  ) tx_subsystem_inst (
      .dma_clk              (dma_aclk),
      .dma_rst              (dma_rst),
      .s_axis_dma_tdata_i   (s_axis_dma_tdata_i),
      .s_axis_dma_tkeep_i   (s_axis_dma_tkeep_i),
      .s_axis_dma_tvalid_i  (s_axis_dma_tvalid_i),
      .s_axis_dma_tlast_i   (s_axis_dma_tlast_i),
      .s_axis_dma_tready_o  (s_axis_dma_tready_o),
      .tx_clk               (tx_aclk),
      .tx_rst               (tx_rst),
      .m_axis_pcs_tdata_o   (m_axis_pcs_tdata_o),
      .m_axis_pcs_tkeep_o   (m_axis_pcs_tkeep_o),
      .m_axis_pcs_tvalid_o  (m_axis_pcs_tvalid_o),
      .m_axis_pcs_tlast_o   (m_axis_pcs_tlast_o),
      .m_axis_pcs_tready_i  (m_axis_pcs_tready_i)
  );

endmodule
