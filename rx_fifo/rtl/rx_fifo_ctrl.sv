module rx_fifo_ctrl
  import rx_fifo_pkg::*;
#(
    parameter  S_DATA_W = 64,
    localparam S_MASK_W = S_DATA_W / BYTE_W
) (
    input  logic                               s_clk,
    input  logic                               s_rst,
    input  logic                               m_clk,
    input  logic                               m_rst,
    input  logic                [S_DATA_W-1:0] data_i,
    input  logic                [S_MASK_W-1:0] mask_i,
    input  logic                               valid_i,
    input  logic                               drop_i,
    input  logic                               send_i,
    output logic                               cancel_o,
           axi_stream_if.master                m_axi
);

  localparam M_DATA_W = m_axi.DATA_W;
  localparam M_MASK_W = m_axi.MASK_W;

  localparam OUTPUT_SCALE = M_MASK_W / S_MASK_W;
  localparam BUFF_COUNT_W = (OUTPUT_SCALE > 1) ? $clog2(OUTPUT_SCALE) : 1;

  logic [    M_DATA_W-1:0] data_buff_d;
  logic [    M_DATA_W-1:0] data_buff_q;

  logic [    M_MASK_W-1:0] mask_buff_d;
  logic [    M_MASK_W-1:0] mask_buff;
  logic [    M_MASK_W-1:0] mask_buff_q;

  logic [BUFF_COUNT_W-1:0] buff_counter_d;
  logic [BUFF_COUNT_W-1:0] buff_counter_q;

  logic                    wr_fifo;
  logic                    commit_data;
  logic                    revert_data;
  logic                    fifo_full;

  always_comb begin
    wr_fifo        = '0;
    commit_data    = '0;
    revert_data    = '0;

    buff_counter_d = buff_counter_q;
    data_buff_d    = data_buff_q;

    mask_buff      = mask_buff_q;
    mask_buff_d    = mask_buff;


    if (drop_i) begin
      revert_data    = 1'b1;
      buff_counter_d = '0;
      mask_buff_d    = '0;
    end else begin
      if (valid_i) begin
        buff_counter_d = buff_counter_q + 1;
        data_buff_d    = {data_i, data_buff_q[M_DATA_W-1:S_DATA_W]};
        mask_buff      = {mask_i, mask_buff_q[M_MASK_W-1:S_MASK_W]};
        mask_buff_d    = mask_buff;
      end

      if (fifo_full && (valid_i || send_i)) begin
        revert_data    = 1'b1;
        buff_counter_d = '0;
        mask_buff_d    = '0;
      end else if (send_i) begin
        commit_data    = 1'b1;
        wr_fifo        = 1'b1;
        buff_counter_d = '0;
        mask_buff_d    = '0;
      end else if (valid_i && buff_counter_q == OUTPUT_SCALE - 1) begin
        wr_fifo        = 1'b1;
        buff_counter_d = '0;
        mask_buff_d    = '0;
      end
    end
  end

  always_ff @(posedge s_clk) begin
    if (s_rst) begin
      mask_buff_q    <= '0;
      buff_counter_q <= '0;
    end else begin
      data_buff_q    <= data_buff_d;
      mask_buff_q    <= mask_buff_d;
      buff_counter_q <= buff_counter_d;
    end
  end

  rx_async_fifo #(
      .ROW_BYTE_LEN(M_MASK_W),
      .FIFO_DEPTH  (32)
  ) rx_async_fifo_inst (
      .m_clk   (m_clk),
      .m_rst   (m_rst),
      .s_clk   (s_clk),
      .s_rst   (s_rst),
      .data_i  (data_buff_d),
      .mask_i  (mask_buff),
      .wr_en_i (wr_fifo),
      .commit_i(commit_data),
      .revert_i(revert_data),
      .full_o  (fifo_full),
      .m_axi   (m_axi)
  );

  assign cancel_o = revert_data;

endmodule
