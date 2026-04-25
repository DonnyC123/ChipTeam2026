module tx_subsystem_tb_top #(
    parameter int MAX_BURST_BEATS = 256
);

  localparam int DMA_DATA_W  = 256;
  localparam int DMA_VALID_W = 32;
  localparam int PCS_DATA_W  = 64;
  localparam int PCS_VALID_W = 8;
  localparam int FIFO_DEPTH  = 32;
  localparam int NUM_QUEUES  = 4;
  localparam int QID_W       = (NUM_QUEUES > 1) ? $clog2(NUM_QUEUES) : 1;

  logic                  clk;
  logic                  rst;

  logic [DMA_DATA_W-1:0] s_axis_dma_tdata_i;
  logic [DMA_VALID_W-1:0] s_axis_dma_tkeep_i;
  logic                  s_axis_dma_tvalid_i;
  logic                  s_axis_dma_tlast_i;
  logic [QID_W-1:0]      s_axis_dma_tdest_i;
  logic                  s_axis_dma_tready_o;

  logic                  m_axis_tready_i;
  logic [PCS_DATA_W-1:0] m_axis_tdata_o;
  logic [PCS_VALID_W-1:0] m_axis_tkeep_o;
  logic                  m_axis_tvalid_o;
  logic                  m_axis_tlast_o;

  tx_axis_if #(
      .DATA_W    (DMA_DATA_W),
      .KEEP_W    (DMA_VALID_W),
      .DEST_W    (QID_W)
  ) s_axis_dma_if ();

  tx_axis_if #(
      .DATA_W    (PCS_DATA_W),
      .KEEP_W    (PCS_VALID_W),
      .DEST_W    (1)
  ) m_axis_pcs_if ();

  assign s_axis_dma_if.tdata  = s_axis_dma_tdata_i;
  assign s_axis_dma_if.tkeep  = s_axis_dma_tkeep_i;
  assign s_axis_dma_if.tvalid = s_axis_dma_tvalid_i;
  assign s_axis_dma_if.tlast  = s_axis_dma_tlast_i;
  assign s_axis_dma_if.tdest  = s_axis_dma_tdest_i;
  assign s_axis_dma_tready_o  = s_axis_dma_if.tready;

  assign m_axis_pcs_if.tready = m_axis_tready_i;
  assign m_axis_tdata_o       = m_axis_pcs_if.tdata;
  assign m_axis_tkeep_o       = m_axis_pcs_if.tkeep;
  assign m_axis_tvalid_o      = m_axis_pcs_if.tvalid;
  assign m_axis_tlast_o       = m_axis_pcs_if.tlast;

  tx_subsystem #(
      .FIFO_DEPTH     (FIFO_DEPTH),
      .NUM_QUEUES     (NUM_QUEUES),
      .MAX_BURST_BEATS (MAX_BURST_BEATS)
  ) dut (
      .clk           (clk),
      .rst           (rst),
      .s_axis_dma_if (s_axis_dma_if),
      .m_axis_pcs_if (m_axis_pcs_if)
  );

endmodule
