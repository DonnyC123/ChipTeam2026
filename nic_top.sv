`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Module Name: nic_top
// Description: Top-level for AS02MC04 25G Ethernet NIC with PCIe DMA
//////////////////////////////////////////////////////////////////////////////////

module nic_top (
    // System clock (100 MHz differential, E18/D18)
    input  wire diff_100mhz_clk_p,
    input  wire diff_100mhz_clk_n,

    // SFP MGT refclk (156.25 MHz differential, K7/K6)
    input  wire sfp_mgt_clk_p,
    input  wire sfp_mgt_clk_n,

    // SFP_1 serial pins (Bank 227, channel X0Y15)
    input  wire sfp_1_rxp,
    input  wire sfp_1_rxn,
    output wire sfp_1_txp,
    output wire sfp_1_txn,

    // SFP_1 control/status
    input  wire sfp_1_mod_def_0,
    input  wire sfp_1_tx_fault,
    input  wire sfp_1_los,
    output wire sfp_1_led,

    // PCIe
    input  wire [7:0] pci_express_x8_rxn,
    input  wire [7:0] pci_express_x8_rxp,
    output wire [7:0] pci_express_x8_txn,
    output wire [7:0] pci_express_x8_txp,
    input  wire       pcie_perstn,
    input  wire       pcie_refclk_clk_p,
    input  wire       pcie_refclk_clk_n,

    // Status LEDs
    output wire [3:0] gpio_led
);

    localparam int NUM_BYTE = 32;
    localparam int DATA_W   = NUM_BYTE * 8;

    axi_stream_if #(.DATA_W(DATA_W)) rx_axi_stream();

    // ?????????????????????????????????????????????
    // Free-running clock + MGT refclk
    // ?????????????????????????????????????????????
    wire freerun_clk;
    IBUFDS u_sysclk_buf (
        .I  (diff_100mhz_clk_p),
        .IB (diff_100mhz_clk_n),
        .O  (freerun_clk)
    );

    wire mgtrefclk_227;
    IBUFDS_GTE4 #(
        .REFCLK_EN_TX_PATH  (1'b0),
        .REFCLK_HROW_CK_SEL (2'b00),
        .REFCLK_ICNTL_RX    (2'b00)
    ) u_mgtrefclk_buf (
        .I    (sfp_mgt_clk_p),
        .IB   (sfp_mgt_clk_n),
        .CEB  (1'b0),
        .O    (mgtrefclk_227),
        .ODIV2()
    );

    // ?????????????????????????????????????????????
    // Power-on reset
    // ?????????????????????????????????????????????
    reg [7:0] por_cnt     = 8'h00;
    reg       freerun_rst = 1'b1;
    always @(posedge freerun_clk) begin
        if (por_cnt != 8'hFF) begin
            por_cnt     <= por_cnt + 1;
            freerun_rst <= 1'b1;
        end else begin
            freerun_rst <= 1'b0;
        end
    end

    // ?????????????????????????????????????????????
    // PCIe block design
    // ?????????????????????????????????????????????
    wire        axi_aclk;
    wire        axi_aresetn;
    wire        axi_rst = ~axi_aresetn;

    wire [DATA_W-1:0]    h2c_tdata;
    wire [NUM_BYTE-1:0]  h2c_tkeep;
    wire                 h2c_tvalid;
    wire                 h2c_tlast;
    wire                 h2c_tready;


design_1_wrapper design_1_wrapper_inst (
    // PCIe physical interface
    .pci_express_x8_rxn   (pci_express_x8_rxn),
    .pci_express_x8_rxp   (pci_express_x8_rxp),
    .pci_express_x8_txn   (pci_express_x8_txn),
    .pci_express_x8_txp   (pci_express_x8_txp),
    .pcie_perstn          (pcie_perstn),
    .pcie_refclk_clk_n    (pcie_refclk_clk_n),
    .pcie_refclk_clk_p    (pcie_refclk_clk_p),
    .axi_aclk             (axi_aclk),
    .axi_aresetn          (axi_aresetn),
    .M_AXIS_H2C_0_0_tdata  (h2c_tdata),
    .M_AXIS_H2C_0_0_tkeep  (h2c_tkeep),
    .M_AXIS_H2C_0_0_tvalid (h2c_tvalid),
    .M_AXIS_H2C_0_0_tlast  (h2c_tlast),
    .M_AXIS_H2C_0_0_tready (h2c_tready),
    .S_AXIS_C2H_0_0_tdata  (rx_axi_stream.data),
    .S_AXIS_C2H_0_0_tkeep  (rx_axi_stream.mask),
    .S_AXIS_C2H_0_0_tvalid (rx_axi_stream.valid),
    .S_AXIS_C2H_0_0_tlast  (rx_axi_stream.last),
    .S_AXIS_C2H_0_0_tready (rx_axi_stream.ready)
);

    // ?????????????????????????????????????????????
    // GT wizard
    // ?????????????????????????????????????????????
    wire        tx_usrclk;
    wire        rx_usrclk;
    wire        tx_userclk_active;
    wire        rx_userclk_active;
    wire        gt_powergood;
    wire        tx_reset_done;
    wire        rx_reset_done;
    wire        rx_cdr_stable;

    wire [63:0] gt_tx_data;
    wire [63:0] gt_rx_data;
    wire rx_locked;
    wire rx_bitslip;
    
    // loopback_mode now driven from VIO over JTAG (see u_vio below)
    wire [2:0]  loopback_mode;

    gtwizard_ultrascale_0 u_gt (
        .gtwiz_reset_clk_freerun_in        (freerun_clk),
        .gtwiz_reset_all_in                (freerun_rst),
        .gtwiz_reset_tx_pll_and_datapath_in(1'b0),
        .gtwiz_reset_tx_datapath_in        (1'b0),
        .gtwiz_reset_rx_pll_and_datapath_in(1'b0),
        .gtwiz_reset_rx_datapath_in        (1'b0),
        .gtwiz_userclk_tx_reset_in         (freerun_rst),
        .gtwiz_userclk_rx_reset_in         (freerun_rst),

        .gtwiz_userclk_tx_srcclk_out       (),
        .gtwiz_userclk_tx_usrclk_out       (),
        .gtwiz_userclk_tx_usrclk2_out      (tx_usrclk),
        .gtwiz_userclk_tx_active_out       (tx_userclk_active),
        .gtwiz_userclk_rx_srcclk_out       (),
        .gtwiz_userclk_rx_usrclk_out       (),
        .gtwiz_userclk_rx_usrclk2_out      (rx_usrclk),
        .gtwiz_userclk_rx_active_out       (rx_userclk_active),

        .gtrefclk00_in                     (mgtrefclk_227),
        .gtyrxp_in                         (sfp_1_rxp),
        .gtyrxn_in                         (sfp_1_rxn),
        .gtytxp_out                        (sfp_1_txp),
        .gtytxn_out                        (sfp_1_txn),

        .gtwiz_userdata_tx_in              (gt_tx_data),
        .gtwiz_userdata_rx_out             (gt_rx_data),

        .loopback_in                       (loopback_mode),
        .rxslide_in                        (rx_bitslip),

        .gtpowergood_out                   (gt_powergood),
        .gtwiz_reset_tx_done_out           (tx_reset_done),
        .gtwiz_reset_rx_done_out           (rx_reset_done),
        .gtwiz_reset_rx_cdr_stable_out     (rx_cdr_stable),
        .rxpmaresetdone_out                (),
        .txpmaresetdone_out                (),

        .qpll0outclk_out                   (),
        .qpll0outrefclk_out                ()
    );

    // ?????????????????????????????????????????????
    // RX-domain reset
    // ?????????????????????????????????????????????
    wire      rx_ready_async = rx_reset_done & rx_userclk_active & gt_powergood;
    reg [3:0] rx_rst_sync    = 4'hF;
    always @(posedge rx_usrclk or negedge rx_ready_async) begin
        if (!rx_ready_async) rx_rst_sync <= 4'hF;
        else                 rx_rst_sync <= {rx_rst_sync[2:0], 1'b0};
    end
    wire rx_pcs_rst = rx_rst_sync[3];

    // ?????????????????????????????????????????????
    // TX-domain reset
    // ?????????????????????????????????????????????
    wire      tx_ready_async = tx_reset_done & tx_userclk_active & gt_powergood;
    reg [3:0] tx_rst_sync    = 4'hF;
    always @(posedge tx_usrclk or negedge tx_ready_async) begin
        if (!tx_ready_async) tx_rst_sync <= 4'hF;
        else                 tx_rst_sync <= {tx_rst_sync[2:0], 1'b0};
    end
    wire tx_pcs_rst = tx_rst_sync[3];

    // ?????????????????????????????????????????????
    // RX top
    // ?????????????????????????????????????????????


    rx_top #(
        .DIN_W       (64),
        .GOOD_COUNT  (64),
        .BAD_COUNT   (8),
        .BITSLIP_WAIT(40)
    ) rx_top_inst (
        .rx_clk      (rx_usrclk),
        .rx_rst      (rx_pcs_rst),
        .axi_clk     (axi_aclk),
        .axi_rst     (axi_rst),
        .raw_data_i  (gt_rx_data),
        .raw_valid_i (1'b1),
        .locked_o    (rx_locked),
        .bitslip_o   (rx_bitslip),
        .m_axi       (rx_axi_stream.master)
    );

    // ?????????????????????????????????????????????
    // TX CDC: DMA (axi_aclk) ? GT TX (tx_usrclk)
    // ?????????????????????????????????????????????
    wire [63:0] tx_raw_data;
    wire        tx_raw_valid;
    wire        tx_raw_ready;

    tx_cdc_top #(
        .FIFO_DEPTH      (64),
        .DESC_DEPTH      (32),
        .NUM_QUEUES      (4),
        .MAX_BURST_BEATS (256)
    ) tx_cdc_top_inst (
        .dma_clk             (axi_aclk),
        .dma_rst             (axi_rst),
        .clk                 (tx_usrclk),
        .rst                 (tx_pcs_rst),
        .s_axis_dma_tdata_i  (h2c_tdata),
        .s_axis_dma_tkeep_i  (h2c_tkeep),
        .s_axis_dma_tvalid_i (h2c_tvalid),
        .s_axis_dma_tlast_i  (h2c_tlast),
        .s_axis_dma_tready_o (h2c_tready),
        .raw_data_o          (tx_raw_data),
        .raw_valid_o         (tx_raw_valid),
        .raw_ready_o         (tx_raw_ready)
    );

    assign gt_tx_data = tx_raw_data;

    // ?????????????????????????????????????????????
    // RX AXI-Stream sink fallback
    // ?????????????????????????????????????????????

    reg [31:0] rx_frame_count = 32'h0;
    always @(posedge axi_aclk) begin
        if (axi_rst) rx_frame_count <= 32'h0;
        else if (rx_axi_stream.valid && rx_axi_stream.ready && rx_axi_stream.last)
            rx_frame_count <= rx_frame_count + 1;
    end

    // ?????????????????????????????????????????????
    // Status LEDs
    // ?????????????????????????????????????????????
    assign gpio_led[0] = gt_powergood;
    assign gpio_led[1] = tx_reset_done;
    assign gpio_led[2] = rx_reset_done;
    assign gpio_led[3] = rx_locked;
    assign sfp_1_led   = ~sfp_1_los;

    // ?????????????????????????????????????????????
    // VIO for JTAG-readable status + loopback control
    // ?????????????????????????????????????????????
    vio_status u_vio (
        .clk        (freerun_clk),       // always running, available before PCIe/GT
        .probe_in0  (gt_powergood),
        .probe_in1  (tx_reset_done),
        .probe_in2  (rx_reset_done),
        .probe_in3  (rx_locked),
        .probe_in4  (sfp_1_los),
        .probe_in5  (sfp_1_tx_fault),
        .probe_in6  (sfp_1_mod_def_0),   // 0 = module present, 1 = absent
        .probe_in7  (rx_cdr_stable),
        .probe_out0 (loopback_mode)      // 3-bit: 000=normal, 001=PCS lb, 010=PMA lb
    );

endmodule
