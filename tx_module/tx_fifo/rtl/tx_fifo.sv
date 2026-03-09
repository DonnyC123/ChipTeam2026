module tx_fifo #(
    parameter int DMA_DATA_W  = tx_fifo_pkg::DMA_DATA_W,
    parameter int DMA_VALID_W = tx_fifo_pkg::DMA_VALID_W,
    parameter int PCS_DATA_W  = tx_fifo_pkg::PCS_DATA_W,
    parameter int PCS_VALID_W = tx_fifo_pkg::PCS_VALID_W,
    parameter int DEPTH       = tx_fifo_pkg::DEPTH
) (
    input  logic                   clk,
    input  logic                   rst,
    input  logic [DMA_DATA_W-1:0]  dma_data_i,
    input  logic [DMA_VALID_W-1:0] dma_valid_i,
    input  logic                   dma_wr_en_i,
    output logic [PCS_DATA_W-1:0]  pcs_data_o,
    output logic [PCS_VALID_W-1:0] pcs_valid_o,
    input  logic                   pcs_read_i,
    output logic                   empty_o,
    output logic                   full_o,
    input  logic                   sched_req_i,
    output logic                   sched_grant_o
);

  import tx_fifo_pkg::*;

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
  logic                fetch_next;

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

  always_comb begin
    empty = (wr_ptr_q == rd_ptr_q);
    full  = (wr_ptr_q.addr == rd_ptr_q.addr) &&
            (wr_ptr_q.tag != rd_ptr_q.tag);

    empty_o = empty;
    full_o  = full;

    wr_en = dma_wr_en_i && !full;

    wr_ptr_d = wr_ptr_q;
    if (wr_en) begin
      wr_ptr_d = wr_ptr_q + 1;
    end

    fetch_next = pcs_read_i && (beat_cnt_q == (BEATS_PER_WORD - 1));

    rd_ptr_d = rd_ptr_q;
    if (fetch_next && !empty) begin
      rd_ptr_d = rd_ptr_q + 1;
    end

    beat_cnt_d = beat_cnt_q;
    if (pcs_read_i && !empty) begin
      if (beat_cnt_q == (BEATS_PER_WORD - 1)) begin
        beat_cnt_d = '0;
      end else begin
        beat_cnt_d = beat_cnt_q + 1;
      end
    end

    rd_entry = mem[rd_ptr_q.addr];

    pcs_data_o  = '0;
    pcs_valid_o = '0;
    if (!empty) begin
      pcs_data_o  = rd_entry.data[beat_cnt_q * PCS_DATA_W +: PCS_DATA_W];
      pcs_valid_o = rd_entry.valid[beat_cnt_q * PCS_VALID_W +: PCS_VALID_W];
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
      mem[wr_ptr_q.addr] <= '{data: dma_data_i, valid: dma_valid_i};
    end
  end

endmodule