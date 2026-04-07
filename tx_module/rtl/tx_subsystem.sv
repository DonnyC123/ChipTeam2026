interface tx_axis_if #(
    parameter int DATA_W = 64,
    parameter int KEEP_W = DATA_W / 8
);
  logic [DATA_W-1:0] tdata;
  logic [KEEP_W-1:0] tkeep;
  logic              tvalid;
  logic              tready;
  logic              tlast;

  modport source (
      output tdata,
      output tkeep,
      output tvalid,
      output tlast,
      input  tready
  );

  modport sink (
      input  tdata,
      input  tkeep,
      input  tvalid,
      input  tlast,
      output tready
  );
endinterface

module tx_subsystem #(
    parameter int DMA_DATA_W       = 256,
    parameter int DMA_VALID_W      = 32,
    parameter int PCS_DATA_W       = 64,
    parameter int PCS_VALID_W      = 8,
    parameter int FIFO_DEPTH       = 32,
    parameter int NUM_QUEUES       = 2,
    parameter int MAX_BURST_BEATS  = 256
) (
    input  logic                              clk,
    input  logic                              rst,
    input  logic [NUM_QUEUES-1:0]             q_valid_i,
    input  logic [NUM_QUEUES-1:0]             q_last_i,

    // DMA data ingress: AXI-Stream from DMA/MM2S
    input  logic [DMA_DATA_W-1:0]             s_axis_dma_tdata_i,
    input  logic [DMA_VALID_W-1:0]            s_axis_dma_tkeep_i,
    input  logic                              s_axis_dma_tvalid_i,
    input  logic                              s_axis_dma_tlast_i,

    // Request channel toward DMA request generator / queue fetch logic.
    // Tie dma_req_ready_i high when downstream is always ready.
    input  logic                              dma_req_ready_i,

    // AXI-Stream egress to PCS
    tx_axis_if.source                         m_axis_pcs_if,

    // Outputs
    output logic                              s_axis_dma_tready_o,
    output logic                              dma_read_en_o,
    output logic [$clog2(NUM_QUEUES)-1:0]     dma_queue_sel_o
);

  import tx_fifo_pkg::*;

  logic fifo_empty;
  logic fifo_full;
  logic fifo_overflow;
  logic fifo_req;
  logic fifo_grant;
  logic [PCS_DATA_W-1:0] pcs_data;
  logic [PCS_VALID_W-1:0] pcs_valid;
  logic pcs_last;
  logic pcs_read;

  logic [DMA_DATA_W-1:0] fifo_dma_data;
  logic [DMA_VALID_W-1:0] fifo_dma_valid;
  logic fifo_dma_last;
  logic fifo_dma_wr_en;

  logic sched_grant_i;
  logic sched_fifo_full_i;

  // Request/grant contract:
  // 1) tx_scheduling asserts fifo_req_o when it wants one DMA word.
  // 2) fifo_grant indicates FIFO can accept a word this cycle.
  // 3) dma_req_ready_i indicates DMA request path can accept a request this cycle.
  // 4) A request is "accepted" only when both are high in the same cycle.
  //    Accepted request drives dma_read_en_o and queue_sel in the same cycle.
  // 5) If dma_req_ready_i is low, requests can stall; scheduler will retry later.
  assign sched_grant_i = fifo_grant && dma_req_ready_i;

  // Interface width contract (checked at elaboration).
  initial begin
    if (DMA_DATA_W != tx_fifo_pkg::DMA_DATA_W) begin
      $fatal(1, "tx_subsystem: DMA_DATA_W must match tx_fifo_pkg::DMA_DATA_W");
    end
    if (DMA_VALID_W != tx_fifo_pkg::DMA_VALID_W) begin
      $fatal(1, "tx_subsystem: DMA_VALID_W must match tx_fifo_pkg::DMA_VALID_W");
    end
    if (PCS_DATA_W != tx_fifo_pkg::PCS_DATA_W) begin
      $fatal(1, "tx_subsystem: PCS_DATA_W must match tx_fifo_pkg::PCS_DATA_W");
    end
    if (PCS_VALID_W != tx_fifo_pkg::PCS_VALID_W) begin
      $fatal(1, "tx_subsystem: PCS_VALID_W must match tx_fifo_pkg::PCS_VALID_W");
    end
    if ($bits(m_axis_pcs_if.tdata) != PCS_DATA_W) begin
      $fatal(1, "tx_subsystem: m_axis_pcs_if.tdata width mismatch with PCS_DATA_W");
    end
    if ($bits(m_axis_pcs_if.tkeep) != PCS_VALID_W) begin
      $fatal(1, "tx_subsystem: m_axis_pcs_if.tkeep width mismatch with PCS_VALID_W");
    end
  end

  assign m_axis_pcs_if.tdata  = pcs_data;
  assign m_axis_pcs_if.tkeep  = pcs_valid;
  assign m_axis_pcs_if.tvalid = !fifo_empty;
  assign m_axis_pcs_if.tlast  = pcs_last;
  assign pcs_read             = m_axis_pcs_if.tvalid && m_axis_pcs_if.tready;

  // AXIS ingress only.
  assign s_axis_dma_tready_o = !fifo_full;
  assign fifo_dma_wr_en      = s_axis_dma_tvalid_i && s_axis_dma_tready_o;
  assign fifo_dma_data       = s_axis_dma_tdata_i;
  assign fifo_dma_valid      = s_axis_dma_tkeep_i;
  assign fifo_dma_last       = s_axis_dma_tlast_i;
  assign sched_fifo_full_i   = fifo_full;

  tx_fifo #(
      .DEPTH (FIFO_DEPTH)
  ) tx_fifo_inst (
      .clk          (clk),
      .rst          (rst),
      .dma_data_i   (fifo_dma_data),
      .dma_valid_i  (fifo_dma_valid),
      .dma_last_i   (fifo_dma_last),
      .dma_wr_en_i  (fifo_dma_wr_en),
      .pcs_data_o   (pcs_data),
      .pcs_valid_o  (pcs_valid),
      .pcs_last_o   (pcs_last),
      .pcs_read_i   (pcs_read),
      .empty_o      (fifo_empty),
      .full_o       (fifo_full),
      .overflow_o   (fifo_overflow),
      .sched_req_i  (fifo_req),
      .sched_grant_o(fifo_grant)
  );

  tx_scheduling #(
      .NUM_QUEUES     (NUM_QUEUES),
      .MAX_BURST_BEATS(MAX_BURST_BEATS)
  ) tx_scheduling_inst (
      .clk            (clk),
      .rst            (rst),
      .q_valid_i      (q_valid_i),
      .q_last_i       (q_last_i),
      .fifo_full_i    (sched_fifo_full_i),
      .fifo_grant_i   (sched_grant_i),
      .dma_read_en_o  (dma_read_en_o),
      .dma_queue_sel_o(dma_queue_sel_o),
      .fifo_req_o     (fifo_req)
  );

endmodule
