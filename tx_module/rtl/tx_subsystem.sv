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
    parameter int FIFO_DEPTH       = 32,
    parameter int NUM_QUEUES       = 2,
    parameter int MAX_BURST_BEATS  = 256
) (
    input  logic                              clk,
    input  logic                              rst,
    input  logic [NUM_QUEUES-1:0]             q_valid_i,
    input  logic [NUM_QUEUES-1:0]             q_last_i,

    // DMA data ingress: AXI-Stream from DMA/MM2S
    input  logic [tx_fifo_pkg::DMA_DATA_W-1:0] s_axis_dma_tdata_i,
    input  logic [tx_fifo_pkg::DMA_VALID_W-1:0] s_axis_dma_tkeep_i,
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

  localparam int DMA_DATA_W  = tx_fifo_pkg::DMA_DATA_W;
  localparam int DMA_VALID_W = tx_fifo_pkg::DMA_VALID_W;
  localparam int PCS_DATA_W  = tx_fifo_pkg::PCS_DATA_W;
  localparam int PCS_VALID_W = tx_fifo_pkg::PCS_VALID_W;

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

  // Scheduler/DMA request contract:
  // 1) q_valid_i[n]=1 means queue n has a DMA word available to be requested now.
  // 2) q_last_i[n]=1 marks the FINAL DMA word of queue n.
  // 3) tx_scheduling drives fifo_req and queue_sel combinationally.
  // 4) A DMA request is accepted iff (fifo_grant && dma_req_ready_i) in the same cycle.
  // 5) Accepted request pulses dma_read_en_o with the matching dma_queue_sel_o that cycle.
  // 6) If dma_req_ready_i=0, requests may stall; no dma_read_en_o pulse is allowed.
  assign sched_grant_i = fifo_grant && dma_req_ready_i;

  // Interface width contract (checked at elaboration).
  initial begin
    if ($bits(s_axis_dma_tdata_i) != tx_fifo_pkg::DMA_DATA_W) begin
      $fatal(1, "tx_subsystem: s_axis_dma_tdata_i width mismatch with tx_fifo_pkg::DMA_DATA_W");
    end
    if ($bits(s_axis_dma_tkeep_i) != tx_fifo_pkg::DMA_VALID_W) begin
      $fatal(1, "tx_subsystem: s_axis_dma_tkeep_i width mismatch with tx_fifo_pkg::DMA_VALID_W");
    end
    if ($bits(m_axis_pcs_if.tdata) != tx_fifo_pkg::PCS_DATA_W) begin
      $fatal(1, "tx_subsystem: m_axis_pcs_if.tdata width mismatch with tx_fifo_pkg::PCS_DATA_W");
    end
    if ($bits(m_axis_pcs_if.tkeep) != tx_fifo_pkg::PCS_VALID_W) begin
      $fatal(1, "tx_subsystem: m_axis_pcs_if.tkeep width mismatch with tx_fifo_pkg::PCS_VALID_W");
    end
  end

  assign m_axis_pcs_if.tdata  = pcs_data;
  assign m_axis_pcs_if.tkeep  = pcs_valid;
  assign m_axis_pcs_if.tvalid = !fifo_empty;
  assign m_axis_pcs_if.tlast  = pcs_last;
  assign pcs_read             = m_axis_pcs_if.tvalid && m_axis_pcs_if.tready;

  // AXIS ingress contract:
  // - DMA/MM2S must hold tdata/tkeep/tlast stable while tvalid=1 and tready=0.
  // - Word is accepted only on tvalid&&tready; each accepted 256b word enters tx_fifo.
  // - tlast tags that accepted DMA word; tx_fifo translates it to beat-level last.
  // AXIS egress contract:
  // - m_axis_pcs_if.tvalid is high whenever FIFO is non-empty.
  // - Beat is consumed on tvalid&&tready; ordering is strictly FIFO.
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
