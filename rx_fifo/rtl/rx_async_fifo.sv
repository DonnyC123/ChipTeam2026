module rx_async_fifo
  import rx_fifo_pkg::*;
#(
    parameter ROW_BYTE_LEN = 32,
    parameter DATA_W       = 256,
    parameter MASK_W       = 32,
    parameter FIFO_DEPTH   = 16    // Must be a power of two
) (
    input logic m_clk,
    input logic s_clk,
    input logic rst,

    input  logic                [DATA_W-1:0] data_i,
    input  logic                [MASK_W-1:0] mask_i,
    input  logic                             valid_i,
    input  logic                             wr_en_i,
    input  logic                             commit_i,
    output logic                             full_i,
           axi_stream_if.master              m_axi
);

  localparam ADDR_W     = $clog2(FIFO_DEPTH) + 1;
  localparam SYNC_DEPTH = 2;

  typedef struct packed {
    logic              last;
    logic [MASK_W-1:0] mask;
    logic [DATA_W-1:0] data;
  } fifo_row_t;

  fifo_row_t              fifo_mem      [FIFO_DEPTH];

  logic                   full;
  logic                   empty;

  logic      [ADDR_W-1:0] wr_addr_q;
  logic      [ADDR_W-1:0] rd_addr_q;

  logic      [ADDR_W-1:0] wr_addr_sync_q[SYNC_DEPTH];
  logic      [ADDR_W-1:0] rd_addr_sync_q[SYNC_DEPTH];

  fifo_row_t              rd_row_q;

  always_ff @(posedge s_clk) begin
    if (rst) begin
      wr_addr_q <= '0;
    end else begin
      if (wr_en_i && !full) begin
        fifo_mem[wr_addr_q] <= {commit_i, mask_i, data_i};
        wr_addr_q = wr_addr_q + 1;
      end
    end
  end

  always_ff @(posedge m_clk) begin
    if (rst) begin
      rd_addr_q <= '0;
    end else begin
      if (m_axi.ready && !empty) begin
        rd_row_q  = fifo_mem[rd_addr_q];
        rd_addr_q = rd_addr_q + 1;
      end
    end
  end

  // Two FF wr sync

  always_ff @(posedge m_clk) begin
    if (rst) begin
      wr_addr_sync_q <= '0;
    end else begin
      wr_addr_sync_q <= ;
    end
  end

endmodule
