module rx_async_fifo
  import rx_fifo_pkg::*;
#(
    parameter  ROW_BYTE_LEN = 32,
    parameter  FIFO_DEPTH   = 16,                    // Must be a power of two
    localparam MASK_W       = ROW_BYTE_LEN,
    localparam DATA_W       = ROW_BYTE_LEN * BYTE_W
) (
    input logic m_clk,
    input logic m_rst,
    input logic s_clk,
    input logic s_rst,

    input  logic                [DATA_W-1:0] data_i,
    input  logic                [MASK_W-1:0] mask_i,
    input  logic                             wr_en_i,
    input  logic                             commit_i,
    input  logic                             revert_i,
    output logic                             full_o,
           axi_stream_if.master              m_axi
);

  localparam ADDR_W     = $clog2(FIFO_DEPTH);
  localparam SYNC_DEPTH = 2;

  typedef struct packed {
    logic              last;
    logic [MASK_W-1:0] mask;
    logic [DATA_W-1:0] data;
  } fifo_row_t;

  typedef struct packed {
    logic ovfl;
    logic [ADDR_W-1:0] addr;
  } addr_t;

  fifo_row_t fifo_mem                   [FIFO_DEPTH];

  logic      full;
  logic      empty;
  logic      rd_en;
  logic      wr_en;

  addr_t     wr_addr_d;
  addr_t     wr_addr_q;

  addr_t     rd_addr_d;
  addr_t     rd_addr_q;

  addr_t     commit_addr_d;
  addr_t     commit_addr_q;

  addr_t     commit_addr_sync_gray_q    [SYNC_DEPTH];
  addr_t     rd_addr_sync_gray_q        [SYNC_DEPTH];

  addr_t     wr_addr_gray;
  addr_t     rd_addr_gray;
  addr_t     rd_addr_sync_gray_full_cmp;

  fifo_row_t rd_row_q;

  always_comb begin
    rd_en = m_axi.ready && !empty;
    wr_en = wr_en_i && !full && !revert_i;
  end

  always_comb begin
    wr_addr_d     = wr_addr_q;
    rd_addr_d     = rd_addr_q;
    commit_addr_d = commit_addr_q;

    if (revert_i) begin
      wr_addr_d = commit_addr_q;
    end

    if (wr_en) begin
      wr_addr_d = wr_addr_q + 1;
    end

    if (commit_i) begin
      commit_addr_d = wr_addr_d;
    end

    if (rd_en) begin
      rd_addr_d = rd_addr_q + 1;
    end
  end

  always_ff @(posedge s_clk) begin
    if (s_rst) begin
      wr_addr_q     <= '0;
      commit_addr_q <= '0;
    end else begin
      wr_addr_q     <= wr_addr_d;
      commit_addr_q <= commit_addr_d;
    end
  end

  always_ff @(posedge m_clk) begin
    if (m_rst) begin
      rd_addr_q <= '0;
    end else begin
      rd_addr_q <= rd_addr_d;
    end
  end

  always_ff @(posedge s_clk) begin
    if (wr_en) begin
      fifo_mem[wr_addr_q] <= {commit_i, mask_i, data_i};
    end
  end

  always_ff @(posedge m_clk) begin
    rd_row_q <= fifo_mem[rd_addr_d];
  end

  // Two FF Wr Sync
  always_ff @(posedge m_clk) begin
    if (m_rst) begin
      commit_addr_sync_gray_q <= '{default: '0};
    end else begin
      commit_addr_sync_gray_q[1] <= commit_addr_sync_gray_q[0];
      commit_addr_sync_gray_q[0] <= bin_to_gray(commit_addr_q);
    end
  end

  // Two FF Rd Sync
  always_ff @(posedge s_clk) begin
    if (s_rst) begin
      rd_addr_sync_gray_q <= '{default: '0};
    end else begin
      rd_addr_sync_gray_q[1] <= rd_addr_sync_gray_q[0];
      rd_addr_sync_gray_q[0] <= bin_to_gray(rd_addr_q);
    end
  end

  always_comb begin
    wr_addr_gray = bin_to_gray(wr_addr_q);
    rd_addr_gray = bin_to_gray(rd_addr_q);

    rd_addr_sync_gray_full_cmp = '{
        ovfl: ~rd_addr_sync_gray_q[1].ovfl,
        addr: {~rd_addr_sync_gray_q[1].addr[ADDR_W-1], rd_addr_sync_gray_q[1].addr[ADDR_W-2:0]}
    };

    full = (wr_addr_gray == rd_addr_sync_gray_full_cmp);
    empty = (rd_addr_gray == commit_addr_sync_gray_q[1]);
  end

  assign full_o = full;

  always_comb begin
    m_axi.data  = rd_row_q.data;
    m_axi.mask  = rd_row_q.mask;
    m_axi.last  = rd_row_q.last;
    m_axi.valid = !empty;
  end

endmodule
