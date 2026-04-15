import tx_fifo_pkg::*;

module tx_fifo #(
    parameter int DEPTH = 64
) (
    input  logic                   clk,
    input  logic                   rst,
    input  logic [DMA_DATA_W-1:0]  dma_data_i,
    input  logic [DMA_VALID_W-1:0] dma_valid_i,
    input  logic                   dma_last_i,
    input  logic                   dma_wr_en_i,
    input  logic                   pcs_read_i,
    input  logic                   sched_req_i,
    output logic [PCS_DATA_W-1:0]  pcs_data_o,
    output logic [PCS_VALID_W-1:0] pcs_valid_o,
    output logic                   pcs_last_o,
    output logic                   empty_o,
    output logic                   full_o,
    output logic                   overflow_o,
    output logic                   sched_grant_o
);
  // FIFO interface contract:
  // Ingress:
  // - dma_data_i/dma_valid_i/dma_last_i are sampled only when dma_wr_en_i && !full.
  // - If dma_wr_en_i when full, word is dropped and overflow_o pulses for observability.
  // Egress:
  // - pcs_data_o/pcs_valid_o/pcs_last_o present the current 64b beat of head word.
  // - Head advances on read of the current word's terminal beat.
  // - pcs_last_o can assert only on the terminal valid beat of dma_last_i=1 words.
  // Scheduler sideband:
  // - sched_grant_o indicates FIFO can accept a new word this cycle (not a pop grant).

  localparam int PTR_W                = $clog2(DEPTH);
  localparam int BEATS_PER_WORD       = DMA_DATA_W / PCS_DATA_W;
  localparam int VALID_BEATS_PER_WORD = DMA_VALID_W / PCS_VALID_W;
  localparam int BEAT_CNT_W           = (BEATS_PER_WORD > 1) ? $clog2(BEATS_PER_WORD) : 1;

  typedef struct packed {
    logic             tag;
    logic [PTR_W-1:0] addr;
  } tagged_addr_t;

  fifo_entry_t         mem [DEPTH];

  tagged_addr_t        wr_ptr_d, wr_ptr_q;
  tagged_addr_t        rd_ptr_d, rd_ptr_q;

  logic                full, empty;
  logic                wr_en;

  fifo_entry_t         rd_entry;
  logic [BEAT_CNT_W-1:0] beat_cnt_d, beat_cnt_q;
  logic [BEAT_CNT_W-1:0] terminal_beat_idx;
  logic [BEAT_CNT_W-1:0] last_valid_beat_idx;
  logic                rd_last_word_has_valid;
  logic                head_pop;

`ifndef SYNTHESIS
  initial begin
    if ((DMA_DATA_W % PCS_DATA_W) != 0) begin
      $fatal(1, "tx_fifo: DMA_DATA_W must be an integer multiple of PCS_DATA_W");
    end
    if ((DMA_VALID_W % PCS_VALID_W) != 0) begin
      $fatal(1, "tx_fifo: DMA_VALID_W must be an integer multiple of PCS_VALID_W");
    end
    if (BEATS_PER_WORD != VALID_BEATS_PER_WORD) begin
      $fatal(1, "tx_fifo: data/valid beat ratios must match");
    end
    if ((DEPTH < 2) || ((DEPTH & (DEPTH - 1)) != 0)) begin
      $fatal(1, "tx_fifo: DEPTH must be a power of 2 and >= 2");
    end
  end
`endif

  always_comb begin
    empty = (wr_ptr_q == rd_ptr_q);
    full  = (wr_ptr_q.addr == rd_ptr_q.addr) &&
            (wr_ptr_q.tag != rd_ptr_q.tag);

    empty_o = empty;
    full_o  = full;

    wr_en = dma_wr_en_i && !full;
    overflow_o = dma_wr_en_i && full;

    wr_ptr_d = wr_ptr_q;
    if (wr_en) begin
      wr_ptr_d = wr_ptr_q + 1;
    end

    rd_entry = mem[rd_ptr_q.addr];

    last_valid_beat_idx = '0;
    rd_last_word_has_valid = 1'b0;
    for (int i = 0; i < BEATS_PER_WORD; i++) begin
      if (|rd_entry.valid[i * PCS_VALID_W +: PCS_VALID_W]) begin
        last_valid_beat_idx = BEAT_CNT_W'(i);
        rd_last_word_has_valid = 1'b1;
      end
    end

    if (rd_entry.last) begin
      terminal_beat_idx = rd_last_word_has_valid ? last_valid_beat_idx : '0;
    end else begin
      terminal_beat_idx = BEAT_CNT_W'(BEATS_PER_WORD - 1);
    end

    head_pop = pcs_read_i && !empty && (beat_cnt_q == terminal_beat_idx);

    rd_ptr_d = rd_ptr_q;
    if (head_pop) begin
      rd_ptr_d = rd_ptr_q + 1;
    end

    beat_cnt_d = beat_cnt_q;
    if (pcs_read_i && !empty) begin
      if (beat_cnt_q == terminal_beat_idx) begin
        beat_cnt_d = '0;
      end else begin
        beat_cnt_d = beat_cnt_q + 1;
      end
    end

    pcs_data_o  = '0;
    pcs_valid_o = '0;
    pcs_last_o  = 1'b0;
    if (!empty) begin
      pcs_data_o  = rd_entry.data[beat_cnt_q * PCS_DATA_W +: PCS_DATA_W];
      pcs_valid_o = rd_entry.valid[beat_cnt_q * PCS_VALID_W +: PCS_VALID_W];
      pcs_last_o  = rd_entry.last && rd_last_word_has_valid && (beat_cnt_q == terminal_beat_idx);
    end

    sched_grant_o = sched_req_i && !full;
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      wr_ptr_q   <= '0;
      rd_ptr_q   <= '0;
      beat_cnt_q <= '0;
    end else begin
      wr_ptr_q   <= wr_ptr_d;
      rd_ptr_q   <= rd_ptr_d;
      beat_cnt_q <= beat_cnt_d;
    end
  end

  always_ff @(posedge clk) begin
    if (wr_en) begin
      mem[wr_ptr_q.addr] <= '{data: dma_data_i, valid: dma_valid_i, last: dma_last_i};
    end
  end

`ifndef SYNTHESIS
  property p_overflow_flag_exact;
    @(posedge clk) disable iff (rst)
      overflow_o <-> (dma_wr_en_i && full);
  endproperty
  a_overflow_flag_exact: assert property (p_overflow_flag_exact);

  property p_last_only_on_final_beat;
    @(posedge clk) disable iff (rst)
      pcs_last_o |-> (!empty &&
                      rd_entry.last &&
                      rd_last_word_has_valid &&
                      (beat_cnt_q == terminal_beat_idx));
  endproperty
  a_last_only_on_final_beat: assert property (p_last_only_on_final_beat);

  property p_no_last_on_nonfinal_beat;
    @(posedge clk) disable iff (rst)
      (!empty && rd_entry.last && rd_last_word_has_valid && (beat_cnt_q != terminal_beat_idx))
      |-> !pcs_last_o;
  endproperty
  a_no_last_on_nonfinal_beat: assert property (p_no_last_on_nonfinal_beat);

  property p_last_word_has_valid_beat;
    @(posedge clk) disable iff (rst)
      (!empty && rd_entry.last) |-> rd_last_word_has_valid;
  endproperty
  a_last_word_has_valid_beat: assert property (p_last_word_has_valid_beat);

  property p_empty_read_does_not_advance;
    @(posedge clk) disable iff (rst)
      (empty && pcs_read_i) |=> $stable(rd_ptr_q) && $stable(beat_cnt_q);
  endproperty
  a_empty_read_does_not_advance: assert property (p_empty_read_does_not_advance);

  // Coverage: overflow and last-beat events observed.
  c_overflow_seen: cover property (@(posedge clk) overflow_o);
  c_last_seen: cover property (@(posedge clk) pcs_last_o);
`endif

endmodule
