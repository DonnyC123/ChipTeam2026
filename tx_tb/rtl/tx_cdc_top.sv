module tx_cdc_top #(
    parameter int FIFO_DEPTH      = 64,
    parameter int DESC_DEPTH      = 32,
    parameter int NUM_QUEUES      = 4,
    parameter int MAX_BURST_BEATS = 256,
    parameter int QID_W           = (NUM_QUEUES > 1) ? $clog2(NUM_QUEUES) : 1
) (
    input logic dma_clk,
    input logic dma_rst,
    input logic clk,
    input logic rst,

    input  logic [255:0]     s_axis_dma_tdata_i,
    input  logic [31:0]      s_axis_dma_tkeep_i,
    input  logic             s_axis_dma_tvalid_i,
    input  logic             s_axis_dma_tlast_i,
    input  logic [QID_W-1:0] s_axis_dma_tdest_i,
    output logic             s_axis_dma_tready_o,

    output logic [63:0] raw_data_o,
    output logic        raw_valid_o,
    output logic        raw_ready_o,

    output logic [63:0] pcs_data_o,
    output logic [1:0]  pcs_control_o,
    output logic        pcs_valid_o
);

  tx_axis_if #(
      .DATA_W(64),
      .KEEP_W(8),
      .DEST_W(1)
  ) subsystem_to_pcs_if ();

  logic [63:0] subsystem_tdata;
  logic [7:0]  subsystem_tkeep;
  logic        subsystem_tvalid;
  logic        subsystem_tlast;
  logic        subsystem_tready;

  logic [63:0] crc_tdata;
  logic [7:0]  crc_tkeep;
  logic        crc_tvalid;
  logic        crc_tlast;
  logic        crc_ready;

  logic [65:0] scrambled_66b;
  logic        scrambled_valid;
  logic        debubbler_ready;

  tx_subsystem #(
      .FIFO_DEPTH(FIFO_DEPTH),
      .DESC_DEPTH(DESC_DEPTH)
  ) u_tx_subsystem (
      .dma_clk(dma_clk),
      .dma_rst(dma_rst),
      .s_axis_dma_tdata_i(s_axis_dma_tdata_i),
      .s_axis_dma_tkeep_i(s_axis_dma_tkeep_i),
      .s_axis_dma_tvalid_i(s_axis_dma_tvalid_i),
      .s_axis_dma_tlast_i(s_axis_dma_tlast_i),
      .s_axis_dma_tready_o(s_axis_dma_tready_o),
      .tx_clk(clk),
      .tx_rst(rst),
      .m_axis_pcs_tdata_o(subsystem_tdata),
      .m_axis_pcs_tkeep_o(subsystem_tkeep),
      .m_axis_pcs_tvalid_o(subsystem_tvalid),
      .m_axis_pcs_tlast_o(subsystem_tlast),
      .m_axis_pcs_tready_i(subsystem_tready)
  );

  crc_inserter u_crc_inserter (
      .clk(clk),
      .rst(rst),
      .data_i(subsystem_tdata),
      .mask_i(subsystem_tkeep),
      .valid_i(subsystem_tvalid),
      .last_i(subsystem_tlast),
      .ready_i(subsystem_to_pcs_if.tready),
      .ready_o(crc_ready),
      .data_o(crc_tdata),
      .mask_o(crc_tkeep),
      .valid_o(crc_tvalid),
      .last_o(crc_tlast)
  );

  assign subsystem_tready = crc_ready;

  assign subsystem_to_pcs_if.tdata  = crc_tdata;
  assign subsystem_to_pcs_if.tkeep  = crc_tkeep;
  assign subsystem_to_pcs_if.tvalid = crc_tvalid;
  assign subsystem_to_pcs_if.tlast  = crc_tlast;
  assign subsystem_to_pcs_if.tdest  = '0;

  pcs_generator u_pcs_generator (
      .clk(clk),
      .rst(rst),
      .out_ready_i(debubbler_ready),
      .out_data_o(pcs_data_o),
      .out_control_o(pcs_control_o),
      .out_valid_o(pcs_valid_o),
      .axis_slave_if(subsystem_to_pcs_if)
  );

  scrambler #(
      .BIT_IN_W (64),
      .BIT_OUT_W(66),
      .HEAD_W   (2),
      .STATE_W  (58)
  ) u_scrambler (
      .clk(clk),
      .rst(rst),
      ._64b_i(pcs_data_o),
      .valid_i(pcs_valid_o),
      ._2b_header_i(pcs_control_o),
      ._66b_o(scrambled_66b),
      .valid_o(scrambled_valid)
  );

  debubbler #(
      .BIT_IN_W (66),
      .BIT_OUT_W(64)
  ) u_debubbler (
      .clk(clk),
      .rst(rst),
      ._66b_i(scrambled_66b),
      .valid_i(scrambled_valid),
      ._64b_o(raw_data_o),
      .valid_o(raw_valid_o),
      .ready_o(debubbler_ready)
  );

  assign raw_ready_o = debubbler_ready;

endmodule
