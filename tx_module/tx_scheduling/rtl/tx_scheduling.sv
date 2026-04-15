module tx_scheduling #(
    parameter int NUM_QUEUES = tx_scheduling_pkg::NUM_QUEUES,
    parameter int MAX_BURST_BEATS = 256
) (
    input  logic                          clk,
    input  logic                          rst,
    input  logic [NUM_QUEUES-1:0]         q_valid_i,
    input  logic [NUM_QUEUES-1:0]         q_last_i,
    input  logic                          fifo_full_i,
    input  logic                          fifo_grant_i,
    output logic                          dma_read_en_o,
    output logic [$clog2(NUM_QUEUES)-1:0] dma_queue_sel_o,
    output logic                          fifo_req_o
);
  // Scheduler contract:
  // - q_valid_i[n]=1: queue n currently has a DMA word ready.
  // - q_last_i[n]=1: that offered word is the final word of the frame.
  // - fifo_req_o + dma_queue_sel_o are combinational for the current cycle.
  // - A read is issued only on (fifo_req_o && fifo_grant_i && !fifo_full_i).
  // - If grant/space is missing, fifo_req_o may stay high while dma_read_en_o=0.
  // - Fairness guard: if q_last_i is never observed for a served queue,
  //   MAX_BURST_BEATS forces rotation back to IDLE.

  import tx_scheduling_pkg::*;

  localparam int QID_W = $clog2(NUM_QUEUES);
  localparam int BURST_CNT_W = (MAX_BURST_BEATS > 1) ? $clog2(MAX_BURST_BEATS) : 1;

  state_t           state_d, state_q;
  logic [QID_W-1:0] last_served_d, last_served_q;
  logic             dma_read_en_d;
  logic [QID_W-1:0] queue_sel_d, queue_sel_q;
  logic             fifo_req_next;
  logic [BURST_CNT_W-1:0] burst_cnt_d, burst_cnt_q;

  logic [QID_W-1:0] next_queue;
  logic             next_found;
  int unsigned      rr_raw_idx;
  logic [QID_W-1:0] rr_cand;

  initial begin
    if (MAX_BURST_BEATS < 1) begin
      $fatal(1, "tx_scheduling: MAX_BURST_BEATS must be >= 1");
    end
  end

  // Round-robin priority scan starting from last_served + 1
  always_comb begin : rr_arbiter
    next_found = 1'b0;
    next_queue = '0;
    for (int unsigned i = 0; i < NUM_QUEUES; i++) begin
      rr_raw_idx = (unsigned'(last_served_q) + 1 + i) % NUM_QUEUES;
      rr_cand    = rr_raw_idx[QID_W-1:0];
      if (!next_found && q_valid_i[rr_cand]) begin
        next_queue = rr_cand;
        next_found = 1'b1;
      end
    end
  end

  always_comb begin
    state_d       = state_q;
    last_served_d = last_served_q;
    dma_read_en_d = 1'b0;
    queue_sel_d   = queue_sel_q;
    fifo_req_next = 1'b0;
    burst_cnt_d   = burst_cnt_q;

    case (state_q)

      IDLE: begin
        burst_cnt_d = '0;
        if (!fifo_full_i && next_found) begin
          fifo_req_next = 1'b1;
          queue_sel_d = next_queue;
          if (fifo_grant_i) begin
            dma_read_en_d = 1'b1;
            if (q_last_i[next_queue]) begin
              last_served_d = next_queue;
              burst_cnt_d   = '0;
            end else begin
              state_d     = SERVING;
              burst_cnt_d = 1;
            end
          end
        end
      end

      SERVING: begin
        if (!fifo_full_i && q_valid_i[queue_sel_q]) begin
          fifo_req_next = 1'b1;
          queue_sel_d = queue_sel_q;
          if (fifo_grant_i) begin
            dma_read_en_d = 1'b1;
            if (q_last_i[queue_sel_q] || (burst_cnt_q == (MAX_BURST_BEATS - 1))) begin
              // Safety valve: also force queue rotation when q_last is missing.
              state_d       = IDLE;
              last_served_d = queue_sel_q;
              burst_cnt_d   = '0;
            end else begin
              burst_cnt_d = burst_cnt_q + 1'b1;
            end
          end
        end
      end

      default: state_d = IDLE;

    endcase

    dma_read_en_o   = dma_read_en_d;
    dma_queue_sel_o = queue_sel_d;
    fifo_req_o      = fifo_req_next;
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      state_q       <= IDLE;
      last_served_q <= QID_W'(NUM_QUEUES - 1);
      queue_sel_q   <= '0;
      burst_cnt_q   <= '0;
    end else begin
      state_q       <= state_d;
      last_served_q <= last_served_d;
      queue_sel_q   <= queue_sel_d;
      burst_cnt_q   <= burst_cnt_d;
    end
  end

`ifndef SYNTHESIS
  property p_read_requires_req_and_grant;
    @(posedge clk) disable iff (rst)
      dma_read_en_o |-> (fifo_req_o && fifo_grant_i && !fifo_full_i);
  endproperty
  a_read_requires_req_and_grant: assert property (p_read_requires_req_and_grant);

  property p_watchdog_forces_idle_after_max_burst;
    @(posedge clk) disable iff (rst)
      (state_q == SERVING &&
       !fifo_full_i &&
       fifo_grant_i &&
       q_valid_i[queue_sel_q] &&
       !q_last_i[queue_sel_q] &&
       (burst_cnt_q == (MAX_BURST_BEATS - 1)))
      |=> (state_q == IDLE);
  endproperty
  a_watchdog_forces_idle_after_max_burst: assert property (p_watchdog_forces_idle_after_max_burst);

  // Coverage: watchdog-driven queue rotation has occurred.
  c_watchdog_rotation: cover property (
      @(posedge clk) disable iff (rst)
      (state_q == SERVING &&
       !fifo_full_i &&
       fifo_grant_i &&
       q_valid_i[queue_sel_q] &&
       !q_last_i[queue_sel_q] &&
       (burst_cnt_q == (MAX_BURST_BEATS - 1)))
  );
`endif

endmodule
