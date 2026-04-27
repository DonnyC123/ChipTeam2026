module tx_async_fifo #(
    parameter int DATA_W = 8,
    parameter int DEPTH  = 16
) (
    input  logic              wr_clk_i,
    input  logic              wr_rst_i,
    input  logic [DATA_W-1:0] wr_data_i,
    input  logic              wr_valid_i,
    output logic              wr_ready_o,
    output logic              wr_full_o,

    input  logic              rd_clk_i,
    input  logic              rd_rst_i,
    output logic [DATA_W-1:0] rd_data_o,
    output logic              rd_valid_o,
    input  logic              rd_ready_i,
    output logic              rd_empty_o
);

  localparam int ADDR_W = (DEPTH > 1) ? $clog2(DEPTH) : 1;
  localparam int PTR_W  = ADDR_W + 1;

  logic [DATA_W-1:0] mem [DEPTH];

  logic [PTR_W-1:0] wr_bin_q, wr_bin_d;
  logic [PTR_W-1:0] wr_gray_q, wr_gray_d;
  logic [PTR_W-1:0] rd_bin_q, rd_bin_d;
  logic [PTR_W-1:0] rd_gray_q, rd_gray_d;

  logic [PTR_W-1:0] rd_gray_wr_sync_q1, rd_gray_wr_sync_q2;
  logic [PTR_W-1:0] wr_gray_rd_sync_q1, wr_gray_rd_sync_q2;

  logic wr_full_q, wr_full_d;
  logic wr_push;
  logic rd_empty;
  logic rd_pop;

  function automatic logic [PTR_W-1:0] bin_to_gray(input logic [PTR_W-1:0] bin);
    bin_to_gray = (bin >> 1) ^ bin;
  endfunction

  function automatic logic [PTR_W-1:0] invert_gray_msb2(input logic [PTR_W-1:0] gray);
    invert_gray_msb2 = gray;
    invert_gray_msb2[PTR_W-1] = ~gray[PTR_W-1];
    invert_gray_msb2[PTR_W-2] = ~gray[PTR_W-2];
  endfunction

  assign wr_ready_o = !wr_full_q;
  assign wr_full_o  = wr_full_q;
  assign wr_push    = wr_valid_i && wr_ready_o;

  assign rd_empty_o = rd_empty;
  assign rd_valid_o = !rd_empty;
  assign rd_data_o  = mem[rd_bin_q[ADDR_W-1:0]];
  assign rd_pop     = rd_valid_o && rd_ready_i;

  always_comb begin
    wr_bin_d  = wr_bin_q + PTR_W'(wr_push);
    wr_gray_d = bin_to_gray(wr_bin_d);
    wr_full_d = (wr_gray_d == invert_gray_msb2(rd_gray_wr_sync_q2));

    rd_bin_d  = rd_bin_q + PTR_W'(rd_pop);
    rd_gray_d = bin_to_gray(rd_bin_d);
    rd_empty  = (rd_gray_q == wr_gray_rd_sync_q2);
  end

  always_ff @(posedge wr_clk_i) begin
    if (wr_rst_i) begin
      wr_bin_q           <= '0;
      wr_gray_q          <= '0;
      wr_full_q          <= 1'b0;
      rd_gray_wr_sync_q1 <= '0;
      rd_gray_wr_sync_q2 <= '0;
    end else begin
      rd_gray_wr_sync_q1 <= rd_gray_q;
      rd_gray_wr_sync_q2 <= rd_gray_wr_sync_q1;
      wr_bin_q           <= wr_bin_d;
      wr_gray_q          <= wr_gray_d;
      wr_full_q          <= wr_full_d;
      if (wr_push) begin
        mem[wr_bin_q[ADDR_W-1:0]] <= wr_data_i;
      end
    end
  end

  always_ff @(posedge rd_clk_i) begin
    if (rd_rst_i) begin
      rd_bin_q           <= '0;
      rd_gray_q          <= '0;
      wr_gray_rd_sync_q1 <= '0;
      wr_gray_rd_sync_q2 <= '0;
    end else begin
      wr_gray_rd_sync_q1 <= wr_gray_q;
      wr_gray_rd_sync_q2 <= wr_gray_rd_sync_q1;
      rd_bin_q           <= rd_bin_d;
      rd_gray_q          <= rd_gray_d;
    end
  end

endmodule
