module rx_top_wrapper #(
    parameter DIN_W        = 64,
    parameter M_AXI_W      = 256,
    parameter GOOD_COUNT   = 1,
    parameter BAD_COUNT    = 8,
    parameter BITSLIP_WAIT = 3
) (
    input logic             s_clk,
    input logic             s_rst,
    input logic             m_clk,
    input logic             m_rst,
    input logic [DIN_W-1:0] raw_data_i,
    input logic             raw_valid_i,

    output logic locked_o,
    output logic bitslip_o
);

  axi_stream_if #(.DATA_W(M_AXI_W)) m_axi ();

  rx_top #(
      .DIN_W       (DIN_W),
      .GOOD_COUNT  (GOOD_COUNT),
      .BAD_COUNT   (BAD_COUNT),
      .BITSLIP_WAIT(BITSLIP_WAIT)
  ) rx_top_inst (
      .rx_clk     (s_clk),
      .rx_rst     (s_rst),
      .axi_clk    (m_clk),
      .axi_rst    (m_rst),
      .raw_data_i (raw_data_i),
      .raw_valid_i(raw_valid_i),
      .locked_o   (locked_o),
      .bitslip_o  (bitslip_o),
      .m_axi      (m_axi)
  );

endmodule
