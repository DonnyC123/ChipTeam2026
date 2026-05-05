// Loopback DUT: tx_cdc_top -> wire_emulator -> rx_top.
// Mirrors how nic_top wires the same modules around the GT, with wire_emulator
// standing in for the GT + the cable + the QLogic peer's PCS.

module loopback_top #(
    parameter int OFFSET_BITS     = 17,
    parameter int FIFO_DEPTH      = 64,
    parameter int DESC_DEPTH      = 32,
    parameter int NUM_QUEUES      = 4,
    parameter int MAX_BURST_BEATS = 256,
    parameter int RX_AXI_W        = 256,
    parameter int QID_W           = (NUM_QUEUES > 1) ? $clog2(NUM_QUEUES) : 1
) (
    input  logic                  dma_clk,
    input  logic                  dma_rst,
    input  logic                  pcs_clk,
    input  logic                  pcs_rst,
    input  logic                  axi_clk,
    input  logic                  axi_rst,

    input  logic [255:0]          s_axis_dma_tdata_i,
    input  logic [31:0]           s_axis_dma_tkeep_i,
    input  logic                  s_axis_dma_tvalid_i,
    input  logic                  s_axis_dma_tlast_i,
    input  logic [QID_W-1:0]      s_axis_dma_tdest_i,
    output logic                  s_axis_dma_tready_o,

    output logic [RX_AXI_W-1:0]   m_axis_rx_tdata_o,
    output logic [RX_AXI_W/8-1:0] m_axis_rx_tkeep_o,
    output logic                  m_axis_rx_tvalid_o,
    output logic                  m_axis_rx_tlast_o,
    input  logic                  m_axis_rx_tready_i,

    output logic                  rx_locked_o,
    output logic                  rx_bitslip_o
);

    logic [63:0] tx_raw_data;
    logic        tx_raw_valid;
    logic        tx_raw_ready;

    tx_cdc_top #(
        .FIFO_DEPTH      (FIFO_DEPTH),
        .DESC_DEPTH      (DESC_DEPTH),
        .NUM_QUEUES      (NUM_QUEUES),
        .MAX_BURST_BEATS (MAX_BURST_BEATS)
    ) u_tx (
        .dma_clk             (dma_clk),
        .dma_rst             (dma_rst),
        .clk                 (pcs_clk),
        .rst                 (pcs_rst),
        .s_axis_dma_tdata_i  (s_axis_dma_tdata_i),
        .s_axis_dma_tkeep_i  (s_axis_dma_tkeep_i),
        .s_axis_dma_tvalid_i (s_axis_dma_tvalid_i),
        .s_axis_dma_tlast_i  (s_axis_dma_tlast_i),
        .s_axis_dma_tdest_i  (s_axis_dma_tdest_i),
        .s_axis_dma_tready_o (s_axis_dma_tready_o),
        .raw_data_o          (tx_raw_data),
        .raw_valid_o         (tx_raw_valid),
        .raw_ready_o         (tx_raw_ready)
    );

    logic [63:0] rx_raw_data;
    logic        rx_raw_valid;
    logic        rx_bitslip;

    wire_emulator #(
        .OFFSET_BITS (OFFSET_BITS)
    ) u_wire (
        .clk        (pcs_clk),
        .rst        (pcs_rst),
        .tx_data_i  (tx_raw_data),
        .tx_valid_i (tx_raw_valid),
        .rx_data_o  (rx_raw_data),
        .rx_valid_o (rx_raw_valid),
        .slip_i     (rx_bitslip)
    );

    axi_stream_if #(.DATA_W(RX_AXI_W)) rx_axi();

    rx_top #(
        .DIN_W        (64),
        .GOOD_COUNT   (64),
        .BAD_COUNT    (8),
        .BITSLIP_WAIT (40)
    ) u_rx (
        .rx_clk      (pcs_clk),
        .rx_rst      (pcs_rst),
        .axi_clk     (axi_clk),
        .axi_rst     (axi_rst),
        .raw_data_i  (rx_raw_data),
        .raw_valid_i (rx_raw_valid),
        .locked_o    (rx_locked_o),
        .bitslip_o   (rx_bitslip),
        .m_axi       (rx_axi.master)
    );

    assign rx_bitslip_o       = rx_bitslip;
    assign m_axis_rx_tdata_o  = rx_axi.data;
    assign m_axis_rx_tkeep_o  = rx_axi.mask;
    assign m_axis_rx_tvalid_o = rx_axi.valid;
    assign m_axis_rx_tlast_o  = rx_axi.last;
    assign rx_axi.ready       = m_axis_rx_tready_i;

endmodule
