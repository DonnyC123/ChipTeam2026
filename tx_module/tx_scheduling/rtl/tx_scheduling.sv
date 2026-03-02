module tx_scheduling #(
    parameter int NUM_QUEUES = tx_scheduling_pkg::NUM_QUEUES
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

  import tx_scheduling_pkg::*;

  localparam int QID_W = $clog2(NUM_QUEUES);

  state_t           state_d, state_q;
  logic [QID_W-1:0] last_served_d, last_served_q;
  logic             dma_read_en_d, dma_read_en_q;
  logic [QID_W-1:0] queue_sel_d, queue_sel_q;
  logic             fifo_req_d;

  logic [QID_W-1:0] next_queue;
  logic              next_found;

  // Round-robin priority scan starting from last_served + 1
  always_comb begin : rr_arbiter
    int unsigned raw_idx;
    logic [QID_W-1:0] cand;

    next_found = 1'b0;
    next_queue = '0;
    for (int unsigned i = 0; i < NUM_QUEUES; i++) begin
      raw_idx = (unsigned'(last_served_q) + 1 + i) % NUM_QUEUES;
      cand    = raw_idx[QID_W-1:0];
      if (!next_found && q_valid_i[cand]) begin
        next_queue = cand;
        next_found = 1'b1;
      end
    end
  end

  always_comb begin
    state_d       = state_q;
    last_served_d = last_served_q;
    dma_read_en_d = 1'b0;
    queue_sel_d   = queue_sel_q;
    fifo_req_d    = 1'b0;

    case (state_q)

      IDLE: begin
        if (!fifo_full_i && next_found) begin
          fifo_req_d  = 1'b1;
          queue_sel_d = next_queue;
          if (fifo_grant_i) begin
            dma_read_en_d = 1'b1;
            if (q_last_i[next_queue]) begin
              last_served_d = next_queue;
            end else begin
              state_d = SERVING;
            end
          end
        end
      end

      SERVING: begin
        if (!fifo_full_i && q_valid_i[queue_sel_q]) begin
          fifo_req_d  = 1'b1;
          queue_sel_d = queue_sel_q;
          if (fifo_grant_i) begin
            dma_read_en_d = 1'b1;
            if (q_last_i[queue_sel_q]) begin
              state_d       = IDLE;
              last_served_d = queue_sel_q;
            end
          end
        end
      end

      default: state_d = IDLE;

    endcase

    dma_read_en_o   = dma_read_en_d;
    dma_queue_sel_o = queue_sel_d;
    fifo_req_o      = fifo_req_d;
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      state_q       <= IDLE;
      last_served_q <= QID_W'(NUM_QUEUES - 1);
      dma_read_en_q <= 1'b0;
      queue_sel_q   <= '0;
    end else begin
      state_q       <= state_d;
      last_served_q <= last_served_d;
      dma_read_en_q <= dma_read_en_d;
      queue_sel_q   <= queue_sel_d;
    end
  end

endmodule
