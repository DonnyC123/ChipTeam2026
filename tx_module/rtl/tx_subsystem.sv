module tx_subsystem #(
    parameter int FIFO_DEPTH      = 32,
    parameter int NUM_QUEUES      = 4,
    parameter int MAX_BURST_BEATS = 256
) (
    input logic clk,
    input logic rst,

    tx_axis_if.sink   s_axis_dma_if,
    tx_axis_if.source m_axis_pcs_if
);

  import tx_fifo_pkg::*;
  import tx_subsystem_pkg::*;

  localparam int QID_W = (NUM_QUEUES > 1) ? $clog2(NUM_QUEUES) : 1;

  logic [PCS_DATA_W-1:0]  queue_pcs_data[NUM_QUEUES];
  logic [PCS_VALID_W-1:0] queue_pcs_valid[NUM_QUEUES];
  logic                   queue_pcs_last[NUM_QUEUES];
  logic                   queue_empty[NUM_QUEUES];
  logic                   queue_full[NUM_QUEUES];
  logic                   queue_overflow[NUM_QUEUES];
  logic                   queue_wr_en[NUM_QUEUES];
  logic                   queue_read[NUM_QUEUES];
  logic [NUM_QUEUES-1:0]  sched_q_valid;
  logic [NUM_QUEUES-1:0]  sched_q_last;

  logic             sched_fifo_req;
  logic             sched_read_en;
  logic [QID_W-1:0] sched_queue_sel;

  logic [PCS_DATA_W-1:0]  selected_data;
  logic [PCS_VALID_W-1:0] selected_keep;
  logic                   selected_last;

  logic axis_accept;
  logic ingress_tdest_in_range;
  logic ingress_target_full;
  logic m_axis_pop;
  logic m_axis_accept_new;

  logic [PCS_DATA_W-1:0]  m_axis_data_q, m_axis_data_d;
  logic [PCS_VALID_W-1:0] m_axis_keep_q, m_axis_keep_d;
  logic                   m_axis_last_q, m_axis_last_d;
  logic                   m_axis_valid_q, m_axis_valid_d;

  logic             in_packet_q, in_packet_d;
  logic [QID_W-1:0] packet_tdest_q, packet_tdest_d;

  assign ingress_tdest_in_range = (s_axis_dma_if.tdest < NUM_QUEUES);
  assign axis_accept            = s_axis_dma_if.tvalid && s_axis_dma_if.tready;

  always_comb begin
    ingress_target_full = 1'b1;
    if (ingress_tdest_in_range) begin
      ingress_target_full = queue_full[s_axis_dma_if.tdest];
    end
  end

  // Strict AXIS backpressure:
  // - Accept only when target queue exists and has space.
  assign s_axis_dma_if.tready = ingress_tdest_in_range && !ingress_target_full;

  // Internal scheduling view:
  // - q_valid_i[q]: queue q has at least one beat available.
  // - q_last_i[q]:  the CURRENT head beat in queue q is end-of-packet.
  generate
    for (genvar q = 0; q < NUM_QUEUES; q++) begin : gen_queue_bank
      localparam logic [QID_W-1:0] THIS_Q = QID_W'(q);

      assign queue_wr_en[q]   = axis_accept && (s_axis_dma_if.tdest == THIS_Q);
      assign sched_q_valid[q] = !queue_empty[q];
      assign sched_q_last[q]  = (!queue_empty[q]) && queue_pcs_last[q];
      assign queue_read[q]    = sched_read_en && (sched_queue_sel == THIS_Q);

      tx_fifo #(
          .DEPTH(FIFO_DEPTH)
      ) tx_fifo_q (
          .clk         (clk),
          .rst         (rst),
          .dma_data_i  (s_axis_dma_if.tdata),
          .dma_valid_i (s_axis_dma_if.tkeep),
          .dma_last_i  (s_axis_dma_if.tlast),
          .dma_wr_en_i (queue_wr_en[q]),
          .pcs_data_o  (queue_pcs_data[q]),
          .pcs_valid_o (queue_pcs_valid[q]),
          .pcs_last_o  (queue_pcs_last[q]),
          .pcs_read_i  (queue_read[q]),
          .empty_o     (queue_empty[q]),
          .full_o      (queue_full[q]),
          .overflow_o  (queue_overflow[q]),
          .sched_req_i (1'b0),
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

  assign m_axis_pop        = m_axis_valid_q && m_axis_pcs_if.tready;
  assign m_axis_accept_new = !m_axis_valid_q || m_axis_pop;

  always_comb begin
    m_axis_data_d  = m_axis_data_q;
    m_axis_keep_d  = m_axis_keep_q;
    m_axis_last_d  = m_axis_last_q;
    m_axis_valid_d = m_axis_valid_q;

    if (m_axis_pop) begin
      m_axis_last_d  = 1'b0;
      m_axis_valid_d = 1'b0;
    end

    if (sched_read_en && m_axis_accept_new) begin
      m_axis_data_d  = selected_data;
      m_axis_keep_d  = selected_keep;
      m_axis_last_d  = selected_last;
      m_axis_valid_d = 1'b1;
    end
  end

  assign m_axis_pcs_if.tdata  = m_axis_data_q;
  assign m_axis_pcs_if.tkeep  = m_axis_keep_q;
  assign m_axis_pcs_if.tvalid = m_axis_valid_q;
  assign m_axis_pcs_if.tlast  = m_axis_last_q;
  assign m_axis_pcs_if.tdest  = '0;

  tx_scheduling #(
      .NUM_QUEUES(NUM_QUEUES),
      .MAX_BURST_BEATS(MAX_BURST_BEATS)
  ) tx_scheduling_inst (
      .clk           (clk),
      .rst           (rst),
      .q_valid_i     (sched_q_valid),
      .q_last_i      (sched_q_last),
      .fifo_full_i   (!m_axis_accept_new),
      .fifo_grant_i  (m_axis_accept_new),
      .dma_read_en_o (sched_read_en),
      .dma_queue_sel_o(sched_queue_sel),
      .fifo_req_o    (sched_fifo_req)
  );

  always_comb begin
    in_packet_d    = in_packet_q;
    packet_tdest_d = packet_tdest_q;

    if (axis_accept) begin
      if (!in_packet_q) begin
        packet_tdest_d = s_axis_dma_if.tdest;
      end
      in_packet_d = !s_axis_dma_if.tlast;
    end
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      in_packet_q    <= 1'b0;
      packet_tdest_q <= '0;
      m_axis_data_q  <= '0;
      m_axis_keep_q  <= '0;
      m_axis_last_q  <= 1'b0;
      m_axis_valid_q <= 1'b0;
    end else begin
      in_packet_q    <= in_packet_d;
      packet_tdest_q <= packet_tdest_d;
      m_axis_data_q  <= m_axis_data_d;
      m_axis_keep_q  <= m_axis_keep_d;
      m_axis_last_q  <= m_axis_last_d;
      m_axis_valid_q <= m_axis_valid_d;
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
      (in_packet_q && axis_accept) |-> (s_axis_dma_if.tdest == packet_tdest_q);
  endproperty
  a_tdest_stable_within_packet: assert property (p_tdest_stable_within_packet);

  // Do not accept writes when the addressed queue is full.
  property p_no_accept_when_target_full;
    @(posedge clk) disable iff (rst)
      (s_axis_dma_if.tvalid && ingress_tdest_in_range && ingress_target_full) |-> !s_axis_dma_if.tready;
  endproperty
  a_no_accept_when_target_full: assert property (p_no_accept_when_target_full);

  // AXIS source must hold payload stable while waiting for ready.
  property p_axis_hold_while_wait;
    @(posedge clk) disable iff (rst)
      (s_axis_dma_if.tvalid && !s_axis_dma_if.tready)
      |=> (s_axis_dma_if.tvalid &&
           $stable(s_axis_dma_if.tdata) &&
           $stable(s_axis_dma_if.tkeep) &&
           $stable(s_axis_dma_if.tlast) &&
           $stable(s_axis_dma_if.tdest));
  endproperty
  a_axis_hold_while_wait: assert property (p_axis_hold_while_wait);

  // AXIS byte-enable contract expected by downstream PCS encoder.
  property p_non_last_keep_full;
    @(posedge clk) disable iff (rst)
      (axis_accept && !s_axis_dma_if.tlast) |-> (s_axis_dma_if.tkeep == DMA_KEEP_ALL);
  endproperty
  a_non_last_keep_full: assert property (p_non_last_keep_full);

  property p_last_keep_nonzero;
    @(posedge clk) disable iff (rst)
      (axis_accept && s_axis_dma_if.tlast) |-> (s_axis_dma_if.tkeep != '0);
  endproperty
  a_last_keep_nonzero: assert property (p_last_keep_nonzero);

  property p_last_keep_contiguous;
    @(posedge clk) disable iff (rst)
      (axis_accept && s_axis_dma_if.tlast) |-> keep_is_lsb_contiguous(s_axis_dma_if.tkeep);
  endproperty
  a_last_keep_contiguous: assert property (p_last_keep_contiguous);

  // Scheduler is only allowed to dequeue from a non-empty selected queue.
  property p_scheduler_dequeue_nonempty;
    @(posedge clk) disable iff (rst)
      sched_read_en |-> sched_q_valid[sched_queue_sel];
  endproperty
  a_scheduler_dequeue_nonempty: assert property (p_scheduler_dequeue_nonempty);

  property p_scheduler_read_requires_output_space;
    @(posedge clk) disable iff (rst)
      sched_read_en |-> m_axis_accept_new;
  endproperty
  a_scheduler_read_requires_output_space: assert property (p_scheduler_read_requires_output_space);

  // Packet-end marker cannot assert on an invalid beat.
  property p_last_requires_valid;
    @(posedge clk) disable iff (rst)
      m_axis_pcs_if.tlast |-> m_axis_pcs_if.tvalid;
  endproperty
  a_last_requires_valid: assert property (p_last_requires_valid);

  // Egress payload must be stable while downstream back-pressures.
  property p_m_axis_hold_while_wait;
    @(posedge clk) disable iff (rst)
      (m_axis_pcs_if.tvalid && !m_axis_pcs_if.tready)
      |=> (m_axis_pcs_if.tvalid &&
           $stable(m_axis_pcs_if.tdata) &&
           $stable(m_axis_pcs_if.tkeep) &&
           $stable(m_axis_pcs_if.tlast));
  endproperty
  a_m_axis_hold_while_wait: assert property (p_m_axis_hold_while_wait);

  c_multi_queue_seen: cover property (
      @(posedge clk) disable iff (rst)
      axis_accept && (s_axis_dma_if.tdest != '0)
  );
`endif

endmodule
