module rx_fifo_ctrl (
    input logic               s_clk,
    input logic               m_clk,
    input logic               rst,
          axi_stream_if.slave s_axi,
          axi_stream_if.slave m_axi
);

  localparam S_DATA_W = s_axis.DATA_W;
  localparam S_MASK_W = s_axis.MASK_W;

  localparam M_DATA_W = m_axis.DATA_W;
  localparam M_MASK_W = m_axis.MASK_W;

  localparam OUTPUT_SCALE = M_MASK_W / S_MASK_W;
  localparam BUFF_COUNT_W = $clog2(OUTPUT_SCALE);

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

    if (s_axi.valid && s_axi.ready) begin
      buff_counter_d = buff_counter_q + 1;

      data_buff_d    = data_buff_q << S_DATA_W | s_axi.data;
      mask_buff      = mask_buff_q << S_MASK_W | s_axi.mask;

      if (fifo_full) begin
        revert_data    = 1'b1;
        buff_counter_q = '0;
        mask_buff_d    = '0;
      end else if (s_axi.last) begin
        commit_data    = 1'b1;
        wr_fifo        = 1'b1;
        buff_counter_q = '0;
        mask_buff_d    = '0;
      end else if (buff_counter_q == OUTPUT_SCALE - 1) begin
        wr_fifo        = 1'b1;
        buff_counter_q = '0;
        mask_buff_d    = '0;
      end else begin
        mask_buff_d = mask_buff;
      end
    end
  end

  always_ff @(posedge s_clk) begin
    if (rst) begin
      data_buff_q = '0;
      mask_buff_q = '0;
    end else begin
      data_buff_q = data_buff_d;
      mask_buff_q = mask_buff_d;
    end
  end

  axi_stream_if #(.DATA_W(M_DATA_W)) m_axi_fifo;


endmodule
