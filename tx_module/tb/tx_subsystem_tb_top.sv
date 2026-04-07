module tx_subsystem_tb_top;

  localparam int DMA_DATA_W  = 256;
  localparam int DMA_VALID_W = 32;
  localparam int PCS_DATA_W  = 64;
  localparam int PCS_VALID_W = 8;
  localparam int FIFO_DEPTH  = 32;
  localparam int NUM_QUEUES  = 2;

  logic                              clk;
  logic                              rst;
  logic [NUM_QUEUES-1:0]             q_valid_i;
  logic [NUM_QUEUES-1:0]             q_last_i;

  logic [DMA_DATA_W-1:0]             s_axis_dma_tdata_i;
  logic [DMA_VALID_W-1:0]            s_axis_dma_tkeep_i;
  logic                              s_axis_dma_tvalid_i;
  logic                              s_axis_dma_tlast_i;
  logic                              s_axis_dma_tready_o;

  logic [DMA_DATA_W-1:0]             dma_data_i;
  logic [DMA_VALID_W-1:0]            dma_valid_i;
  logic                              dma_req_ready_i;

  logic                              dma_read_en_o;
  logic [$clog2(NUM_QUEUES)-1:0]     dma_queue_sel_o;

  logic                              m_axis_tready_i;
  logic [PCS_DATA_W-1:0]             m_axis_tdata_o;
  logic [PCS_VALID_W-1:0]            m_axis_tkeep_o;
  logic                              m_axis_tvalid_o;
  logic                              m_axis_tlast_o;

  tx_axis_if #(
      .DATA_W(PCS_DATA_W),
      .KEEP_W(PCS_VALID_W)
  ) m_axis_pcs_if ();

  assign m_axis_pcs_if.tready = m_axis_tready_i;
  assign m_axis_tdata_o       = m_axis_pcs_if.tdata;
  assign m_axis_tkeep_o       = m_axis_pcs_if.tkeep;
  assign m_axis_tvalid_o      = m_axis_pcs_if.tvalid;
  assign m_axis_tlast_o       = m_axis_pcs_if.tlast;

  tx_subsystem #(
      .DMA_DATA_W        (DMA_DATA_W),
      .DMA_VALID_W       (DMA_VALID_W),
      .PCS_DATA_W        (PCS_DATA_W),
      .PCS_VALID_W       (PCS_VALID_W),
      .FIFO_DEPTH        (FIFO_DEPTH),
      .NUM_QUEUES        (NUM_QUEUES),
      .USE_DMA_AXIS_INPUT(1'b1),
      .DMA_RSP_LATENCY   (0)
  ) dut (
      .clk             (clk),
      .rst             (rst),
      .q_valid_i       (q_valid_i),
      .q_last_i        (q_last_i),
      .s_axis_dma_tdata_i (s_axis_dma_tdata_i),
      .s_axis_dma_tkeep_i (s_axis_dma_tkeep_i),
      .s_axis_dma_tvalid_i(s_axis_dma_tvalid_i),
      .s_axis_dma_tlast_i (s_axis_dma_tlast_i),
      .s_axis_dma_tready_o(s_axis_dma_tready_o),
      .dma_data_i      (dma_data_i),
      .dma_valid_i     (dma_valid_i),
      .dma_req_ready_i (dma_req_ready_i),
      .m_axis_pcs_if   (m_axis_pcs_if),
      .dma_read_en_o   (dma_read_en_o),
      .dma_queue_sel_o (dma_queue_sel_o)
  );

endmodule
