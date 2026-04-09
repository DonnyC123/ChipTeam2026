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
    input  logic                                           clk,
    input  logic                                           rst,

    // DMA/MM2S AXI-Stream ingress.
    input  logic [tx_fifo_pkg::DMA_DATA_W-1:0]            s_axis_dma_tdata_i,
    input  logic [tx_fifo_pkg::DMA_VALID_W-1:0]           s_axis_dma_tkeep_i,
    input  logic                                           s_axis_dma_tvalid_i,
    output logic                                           s_axis_dma_tready_o,
    input  logic                                           s_axis_dma_tlast_i,
    input  logic [(NUM_QUEUES > 1 ? $clog2(NUM_QUEUES) : 1)-1:0] s_axis_dma_tdest_i,

    // AXI-Stream egress to PCS.
    tx_axis_if.source                                      m_axis_pcs_if
);

  import tx_fifo_pkg::*;

  localparam int DMA_DATA_W  = tx_fifo_pkg::DMA_DATA_W;
  localparam int DMA_VALID_W = tx_fifo_pkg::DMA_VALID_W;
  localparam int PCS_DATA_W  = tx_fifo_pkg::PCS_DATA_W;
  localparam int PCS_VALID_W = tx_fifo_pkg::PCS_VALID_W;

  localparam int QID_W = (NUM_QUEUES > 1) ? $clog2(NUM_QUEUES) : 1;

  logic [PCS_DATA_W-1:0] queue_pcs_data   [NUM_QUEUES];
  logic [PCS_VALID_W-1:0] queue_pcs_valid [NUM_QUEUES];
  logic                   queue_pcs_last   [NUM_QUEUES];
  logic                   queue_empty      [NUM_QUEUES];
  logic                   queue_full       [NUM_QUEUES];
  logic                   queue_overflow   [NUM_QUEUES];
  logic                   queue_wr_en      [NUM_QUEUES];
  logic                   queue_read       [NUM_QUEUES];
  logic [NUM_QUEUES-1:0]  sched_q_valid;
  logic [NUM_QUEUES-1:0]  sched_q_last;

  logic                   sched_fifo_req;
  logic                   sched_read_en;
  logic [QID_W-1:0]       sched_queue_sel;

  logic [PCS_DATA_W-1:0]  selected_data;
  logic [PCS_VALID_W-1:0] selected_keep;
  logic                   selected_last;

  logic                   axis_accept;
  logic                   ingress_tdest_in_range;
  logic                   ingress_target_full;

  logic                   in_packet_q, in_packet_d;
  logic [QID_W-1:0]       packet_tdest_q, packet_tdest_d;

  // Interface width contract (checked at elaboration).
  initial begin
    if ($bits(s_axis_dma_tdata_i) != tx_fifo_pkg::DMA_DATA_W) begin
      $fatal(1, "tx_subsystem: s_axis_dma_tdata_i width mismatch with tx_fifo_pkg::DMA_DATA_W");
    end
    if ($bits(s_axis_dma_tkeep_i) != tx_fifo_pkg::DMA_VALID_W) begin
      $fatal(1, "tx_subsystem: s_axis_dma_tkeep_i width mismatch with tx_fifo_pkg::DMA_VALID_W");
    end
    if ($bits(s_axis_dma_tdest_i) != QID_W) begin
      $fatal(1, "tx_subsystem: s_axis_dma_tdest_i width mismatch with queue-id width");
    end
    if ($bits(m_axis_pcs_if.tdata) != tx_fifo_pkg::PCS_DATA_W) begin
      $fatal(1, "tx_subsystem: m_axis_pcs_if.tdata width mismatch with tx_fifo_pkg::PCS_DATA_W");
    end
    if ($bits(m_axis_pcs_if.tkeep) != tx_fifo_pkg::PCS_VALID_W) begin
      $fatal(1, "tx_subsystem: m_axis_pcs_if.tkeep width mismatch with tx_fifo_pkg::PCS_VALID_W");
    end
  end

  assign ingress_tdest_in_range = (s_axis_dma_tdest_i < NUM_QUEUES);
  assign axis_accept            = s_axis_dma_tvalid_i && s_axis_dma_tready_o;

  always_comb begin
    ingress_target_full = 1'b1;
    if (ingress_tdest_in_range) begin
      ingress_target_full = queue_full[s_axis_dma_tdest_i];
    end
  end

  // Strict AXIS backpressure:
  // - Accept only when target queue exists and has space.
  assign s_axis_dma_tready_o = ingress_tdest_in_range && !ingress_target_full;

  // Internal scheduling view:
  // - q_valid_i[q]: queue q has at least one beat available.
  // - q_last_i[q]:  the CURRENT head beat in queue q is end-of-packet.
  generate
    for (genvar q = 0; q < NUM_QUEUES; q++) begin : gen_queue_bank
      localparam logic [QID_W-1:0] THIS_Q = QID_W'(q);

      assign queue_wr_en[q]   = axis_accept && (s_axis_dma_tdest_i == THIS_Q);
      assign sched_q_valid[q] = !queue_empty[q];
      assign sched_q_last[q]  = (!queue_empty[q]) && queue_pcs_last[q];
      assign queue_read[q]    = sched_read_en && (sched_queue_sel == THIS_Q);

      tx_fifo #(
          .DEPTH (FIFO_DEPTH)
      ) tx_fifo_q (
          .clk          (clk),
          .rst          (rst),
          .dma_data_i   (s_axis_dma_tdata_i),
          .dma_valid_i  (s_axis_dma_tkeep_i),
          .dma_last_i   (s_axis_dma_tlast_i),
          .dma_wr_en_i  (queue_wr_en[q]),
          .pcs_data_o   (queue_pcs_data[q]),
          .pcs_valid_o  (queue_pcs_valid[q]),
          .pcs_last_o   (queue_pcs_last[q]),
          .pcs_read_i   (queue_read[q]),
          .empty_o      (queue_empty[q]),
          .full_o       (queue_full[q]),
          .overflow_o   (queue_overflow[q]),
          .sched_req_i  (1'b0),
          .sched_grant_o()
      );
    end
  endgenerate

  always_comb begin
    selected_data = '0;
    selected_keep = '0;
    selected_last = 1'b0;

    if (sched_q_valid[sched_queue_sel]) begin
      selected_data = queue_pcs_data[sched_queue_sel];
      selected_keep = queue_pcs_valid[sched_queue_sel];
      selected_last = queue_pcs_last[sched_queue_sel];
    end
  end

  assign m_axis_pcs_if.tdata  = selected_data;
  assign m_axis_pcs_if.tkeep  = selected_keep;
  assign m_axis_pcs_if.tvalid = sched_read_en;
  assign m_axis_pcs_if.tlast  = sched_read_en && selected_last;

  tx_scheduling #(
      .NUM_QUEUES     (NUM_QUEUES),
      .MAX_BURST_BEATS(MAX_BURST_BEATS)
  ) tx_scheduling_inst (
      .clk            (clk),
      .rst            (rst),
      .q_valid_i      (sched_q_valid),
      .q_last_i       (sched_q_last),
      .fifo_full_i    (1'b0),
      .fifo_grant_i   (m_axis_pcs_if.tready),
      .dma_read_en_o  (sched_read_en),
      .dma_queue_sel_o(sched_queue_sel),
      .fifo_req_o     (sched_fifo_req)
  );

  always_comb begin
    in_packet_d    = in_packet_q;
    packet_tdest_d = packet_tdest_q;

    if (axis_accept) begin
      if (!in_packet_q) begin
        packet_tdest_d = s_axis_dma_tdest_i;
      end
      in_packet_d = !s_axis_dma_tlast_i;
    end
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      in_packet_q    <= 1'b0;
      packet_tdest_q <= '0;
    end else begin
      in_packet_q    <= in_packet_d;
      packet_tdest_q <= packet_tdest_d;
    end
  end

`ifndef SYNTHESIS
  // Accepted ingress beat must always target a legal queue.
  property p_tdest_in_range_on_accept;
    @(posedge clk) disable iff (rst)
      axis_accept |-> ingress_tdest_in_range;
  endproperty
  a_tdest_in_range_on_accept: assert property (p_tdest_in_range_on_accept);

  // While in the middle of a packet, accepted beats must keep the same TDEST.
  property p_tdest_stable_within_packet;
    @(posedge clk) disable iff (rst)
      (in_packet_q && axis_accept) |-> (s_axis_dma_tdest_i == packet_tdest_q);
  endproperty
  a_tdest_stable_within_packet: assert property (p_tdest_stable_within_packet);

  // Do not accept writes when the addressed queue is full.
  property p_no_accept_when_target_full;
    @(posedge clk) disable iff (rst)
      (s_axis_dma_tvalid_i && ingress_tdest_in_range && ingress_target_full) |-> !s_axis_dma_tready_o;
  endproperty
  a_no_accept_when_target_full: assert property (p_no_accept_when_target_full);

  // AXIS source must hold payload stable while waiting for ready.
  property p_axis_hold_while_wait;
    @(posedge clk) disable iff (rst)
      (s_axis_dma_tvalid_i && !s_axis_dma_tready_o)
      |=> (s_axis_dma_tvalid_i &&
           $stable(s_axis_dma_tdata_i) &&
           $stable(s_axis_dma_tkeep_i) &&
           $stable(s_axis_dma_tlast_i) &&
           $stable(s_axis_dma_tdest_i));
  endproperty
  a_axis_hold_while_wait: assert property (p_axis_hold_while_wait);

  // Scheduler is only allowed to dequeue from a non-empty selected queue.
  property p_scheduler_dequeue_nonempty;
    @(posedge clk) disable iff (rst)
      sched_read_en |-> sched_q_valid[sched_queue_sel];
  endproperty
  a_scheduler_dequeue_nonempty: assert property (p_scheduler_dequeue_nonempty);

  // Packet-end marker cannot assert on an invalid beat.
  property p_last_requires_valid;
    @(posedge clk) disable iff (rst)
      m_axis_pcs_if.tlast |-> m_axis_pcs_if.tvalid;
  endproperty
  a_last_requires_valid: assert property (p_last_requires_valid);

  c_multi_queue_seen: cover property (
      @(posedge clk) disable iff (rst)
      axis_accept && (s_axis_dma_tdest_i != '0)
  );
`endif

endmodule
