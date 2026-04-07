module tx_subsystem #(
    parameter int DMA_DATA_W       = 256,
    parameter int DMA_VALID_W      = 32,
    parameter int PCS_DATA_W       = 64,
    parameter int PCS_VALID_W      = 8,
    parameter int FIFO_DEPTH       = 32,
    parameter int NUM_QUEUES       = 2,
    parameter int DMA_RSP_LATENCY  = 0
) (
    input  logic                              clk,
    input  logic                              rst,
    input  logic [DMA_DATA_W-1:0]             dma_data_i,
    input  logic [DMA_VALID_W-1:0]            dma_valid_i,
    input  logic [NUM_QUEUES-1:0]             q_valid_i,
    input  logic [NUM_QUEUES-1:0]             q_last_i,
    input  logic                              m_axis_tready_i,
    output logic                              dma_read_en_o,
    output logic [$clog2(NUM_QUEUES)-1:0]     dma_queue_sel_o,
    output logic [PCS_DATA_W-1:0]             m_axis_tdata_o,
    output logic [PCS_VALID_W-1:0]            m_axis_tkeep_o,
    output logic                              m_axis_tvalid_o,
    output logic                              m_axis_tlast_o
);

  logic fifo_empty;
  logic fifo_full;
  logic fifo_req;
  logic fifo_grant;
  logic [PCS_DATA_W-1:0] pcs_data;
  logic [PCS_VALID_W-1:0] pcs_valid;
  logic pcs_last;
  logic pcs_read;
  logic dma_last;
  logic dma_last_aligned;
  logic dma_wr_en;
  logic dma_req_dly_q;
  logic dma_last_dly_q;
  logic sched_fifo_full_i;

  // Optional alignment for DMA data/valid/last return path:
  // 0 = data returns same cycle as dma_read_en_o.
  // 1 = data returns one cycle later.
  always_ff @(posedge clk) begin
    if (rst) begin
      dma_req_dly_q  <= 1'b0;
      dma_last_dly_q <= 1'b0;
    end else begin
      dma_req_dly_q  <= dma_read_en_o;
      dma_last_dly_q <= dma_last;
    end
  end

  assign dma_last      = dma_read_en_o ? q_last_i[dma_queue_sel_o] : 1'b0;
  assign m_axis_tdata_o  = pcs_data;
  assign m_axis_tkeep_o  = pcs_valid;
  assign m_axis_tvalid_o = !fifo_empty;
  assign m_axis_tlast_o  = pcs_last;
  assign pcs_read        = m_axis_tvalid_o && m_axis_tready_i;

  generate
    if (DMA_RSP_LATENCY == 0) begin : gen_dma_rsp_lat0
      assign dma_wr_en         = dma_read_en_o;
      assign dma_last_aligned  = dma_last;
      assign sched_fifo_full_i = fifo_full;
    end else if (DMA_RSP_LATENCY == 1) begin : gen_dma_rsp_lat1
      assign dma_wr_en         = dma_req_dly_q;
      assign dma_last_aligned  = dma_last_dly_q;
      // Conservative backpressure: treat one in-flight DMA response as full.
      assign sched_fifo_full_i = fifo_full || dma_req_dly_q;
    end else begin : gen_dma_rsp_lat_invalid
      initial begin
        $fatal(1, "tx_subsystem: DMA_RSP_LATENCY must be 0 or 1");
      end
      assign dma_wr_en         = dma_read_en_o;
      assign dma_last_aligned  = dma_last;
      assign sched_fifo_full_i = fifo_full;
    end
  endgenerate

  tx_fifo #(
      .DEPTH (FIFO_DEPTH)
  ) tx_fifo_inst (
      .clk          (clk),
      .rst          (rst),
      .dma_data_i   (dma_data_i),
      .dma_valid_i  (dma_valid_i),
      .dma_last_i   (dma_last_aligned),
      .dma_wr_en_i  (dma_wr_en),
      .pcs_data_o   (pcs_data),
      .pcs_valid_o  (pcs_valid),
      .pcs_last_o   (pcs_last),
      .pcs_read_i   (pcs_read),
      .empty_o      (fifo_empty),
      .full_o       (fifo_full),
      .sched_req_i  (fifo_req),
      .sched_grant_o(fifo_grant)
  );

  tx_scheduling #(
      .NUM_QUEUES (NUM_QUEUES)
  ) tx_scheduling_inst (
      .clk            (clk),
      .rst            (rst),
      .q_valid_i      (q_valid_i),
      .q_last_i       (q_last_i),
      .fifo_full_i    (sched_fifo_full_i),
      .fifo_grant_i   (fifo_grant),
      .dma_read_en_o  (dma_read_en_o),
      .dma_queue_sel_o(dma_queue_sel_o),
      .fifo_req_o     (fifo_req)
  );

endmodule
