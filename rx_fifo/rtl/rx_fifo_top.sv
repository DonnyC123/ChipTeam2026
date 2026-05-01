module rx_fifo_top
  import rx_fifo_pkg::*;
#(
    parameter  S_DATA_W = 64,
    parameter  M_DATA_W = 256,
    localparam S_MASK_W = S_DATA_W / BYTE_W
) (
    input  logic                s_clk,
    input  logic                s_rst,
    input  logic                m_clk,
    input  logic                m_rst,
    input  logic [S_DATA_W-1:0] data_i,
    input  logic [S_MASK_W-1:0] mask_i,
    input  logic                valid_i,
    input  logic                drop_i,
    input  logic                send_i,
    output logic                cancel_o
);

  axi_stream_if #(.DATA_W(M_DATA_W)) m_axi ();

  rx_fifo_ctrl #(
      .S_DATA_W(S_DATA_W)
  ) rx_fifo_ctrl_inst (
      .s_clk   (s_clk),
      .s_rst   (s_rst),
      .m_clk   (m_clk),
      .m_rst   (m_rst),
      .data_i  (data_i),
      .mask_i  (mask_i),
      .valid_i (valid_i),
      .drop_i  (drop_i),
      .send_i  (send_i),
      .cancel_o(cancel_o),
      .m_axi   (m_axi)
  );

endmodule
