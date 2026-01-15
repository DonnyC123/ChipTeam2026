module fifo #(
    parameter int DATA_W          = 32,
    parameter int LOG2_FIFO_DEPTH = 12
) (
    input logic            clk,
    input logic            rst,
          fifo_wr_if.slave wr_if,
          fifo_rd_if.slave rd_if
);

  localparam int ADDR_W = LOG2_FIFO_DEPTH;

  typedef struct packed {
    logic              tag;
    logic [ADDR_W-1:0] addr;
  } tagged_addr_t;

  tagged_addr_t tagged_rd_addr_d;
  tagged_addr_t tagged_rd_addr_q;

  tagged_addr_t tagged_wr_addr_d;
  tagged_addr_t tagged_wr_addr_q;

  logic         rd_fifo;
  logic         wr_fifo;

  always_comb begin
    rd_if.empty = (tagged_wr_addr_q == tagged_rd_addr_q);

    wr_if.full  = (tagged_wr_addr_q.addr == tagged_rd_addr_q.addr)
                && (tagged_wr_addr_q.tag != tagged_rd_addr_q.tag);

    rd_fifo = !rd_if.empty && rd_if.rd_en;
    wr_fifo = !wr_if.full && wr_if.wr_en;
  end

  always_comb begin
    tagged_rd_addr_d = tagged_rd_addr_q;
    if (rd_fifo) begin
      tagged_rd_addr_d = tagged_rd_addr_q + 1;
    end

    tagged_wr_addr_d = tagged_wr_addr_q;
    if (wr_fifo) begin
      tagged_wr_addr_d = tagged_wr_addr_q + 1;
    end

  end

  bram #(
      .DATA_W(DATA_W),
      .ADDR_W(LOG2_FIFO_DEPTH)
  ) fifo_bram_inst (
      .clk      (clk),
      .wr_en_i  (wr_fifo),
      .wr_data_i(wr_if.data),
      .wr_addr_i(tagged_wr_addr_q.addr),
      .rd_addr_i(tagged_rd_addr_q.addr),
      .rd_data_o(rd_if.data)
  );

  always_ff @(posedge clk) begin
    if (rst) begin
      tagged_rd_addr_q <= '0;
      tagged_wr_addr_q <= '0;
    end else begin
      tagged_rd_addr_q <= tagged_rd_addr_d;
      tagged_wr_addr_q <= tagged_wr_addr_d;
    end
  end
endmodule
