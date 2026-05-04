module rx_top #(
    parameter int DIN_W        = 64,
    parameter int GOOD_COUNT   = 1,
    parameter int BAD_COUNT    = 8,
    parameter int BITSLIP_WAIT = 3
) (
    input logic             rx_clk,
    input logic             rx_rst,
    input logic             axi_clk,
    input logic             axi_rst,
    input logic [DIN_W-1:0] raw_data_i,
    input logic             raw_valid_i,

    output logic locked_o,
    output logic bitslip_o,

    axi_stream_if.master m_axi
);
  localparam DATA_W = DIN_W;
  localparam PCS_W      = 66;
  localparam HEADER_W   = 2;
  localparam ETH_DATA_W = 64;
  localparam ETH_MASK_W = ETH_DATA_W / 8;

  logic [     PCS_W-1:0] bubbler_data_66;
  logic                  bubbler_valid_66;

  logic [     DIN_W-1:0] descrambled_data_64;
  logic                  descrambled_valid;

  logic [  HEADER_W-1:0] header_bits_q;

  logic                  eth_valid;
  logic [ETH_DATA_W-1:0] eth_data;
  logic [ETH_MASK_W-1:0] eth_valid_mask;

  logic                  cancel_frame;
  logic                  drop_frame;
  logic                  send_frame;

  logic                  valid_reg;
  logic [ETH_DATA_W-1:0] data_reg;
  logic [ETH_MASK_W-1:0] mask_reg;
  logic                  drop_reg;
  logic                  send_reg;

  bubbler #(
      .BIT_IN_W (DIN_W),
      .BIT_OUT_W(PCS_W)
  ) u_bubbler (
      .clk    (rx_clk),
      .rst    (rx_rst),
      ._64b_i (raw_data_i),
      .valid_i(raw_valid_i),
      ._66b_o (bubbler_data_66),
      .valid_o(bubbler_valid_66)
  );

  descrambler #(
      .BIT_W  (DATA_W),
      .STATE_W(58)
  ) u_descrambler (
      .clk    (rx_clk),
      .rst    (rx_rst),
      ._64b_i (bubbler_data_66[DATA_W-1:0]),
      .valid_i(bubbler_valid_66),
      ._64b_o (descrambled_data_64),
      .valid_o(descrambled_valid)
  );

  alignment_finder #(
      .DATA_WIDTH  (PCS_W),
      .GOOD_COUNT  (GOOD_COUNT),
      .BAD_COUNT   (BAD_COUNT),
      .BITSLIP_WAIT(BITSLIP_WAIT)
  ) u_alignment_finder (
      .clk         (rx_clk),
      .rst         (rx_rst),
      .data_valid_i(bubbler_valid_66),
      .data_i      (bubbler_data_66),
      .locked_o    (locked_o),
      .bitslip_o   (bitslip_o)
  );

  ethernet_assembler #(
      .DATA_IN_W (ETH_DATA_W),
      .DATA_OUT_W(ETH_DATA_W)
  ) u_ethernet_assembler (
      .clk           (rx_clk),
      .rst           (rx_rst),
      .in_valid_i    (descrambled_valid),
      .locked_i      (locked_o),
      .cancel_frame_i(cancel_frame),
      .input_data_i  (descrambled_data_64),
      .header_bits_i (header_bits_q),
      .send_o        (send_frame),
      .drop_frame_o  (drop_frame),
      .out_valid_o   (eth_valid),
      .out_data_o    (eth_data),
      .bytes_valid_o (eth_valid_mask)
  );

  crc_checker #(
        .DATA_W (ETH_DATA_W),
        .MASK_W (ETH_DATA_W/8)
    ) u_crc_checker (
        .clk      (rx_clk),
        .rst      (rx_rst),
        .data_i   (eth_data),
        .mask_i   (eth_valid_mask),
        .valid_i  (eth_valid),
        .send_i   (send_frame),
        .drop_i   (drop_frame),
        .cancel_i (cancel_reg), 
        .cancel_o (cancel_frame),
        
        .data_o   (data_reg),
        .mask_o   (mask_reg),
        .valid_o  (valid_reg),
        .send_o   (send_reg),
        .drop_o   (drop_reg)
    );

  rx_fifo_ctrl #(
      .S_DATA_W(ETH_DATA_W)
  ) rx_fifo_ctrl_inst (
      .s_clk   (rx_clk),
      .s_rst   (rx_rst),
      .m_clk   (axi_clk),
      .m_rst   (axi_rst),

      .data_i  (data_reg),
      .mask_i  (mask_reg),
      .valid_i (valid_reg),
      .drop_i  (drop_reg),
      .send_i  (send_reg),
      .cancel_o(cancel_reg),
      .m_axi   (m_axi)
  );

  always_ff @(posedge rx_clk) begin
    if (rx_rst) begin
      header_bits_q <= '0;
    end else begin
      header_bits_q <= bubbler_data_66[65:64];
    end
  end

endmodule

