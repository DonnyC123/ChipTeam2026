`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Module Name: nic_top
// Description: Top-level for AS02MC04 25G Ethernet NIC with PCIe DMA
//////////////////////////////////////////////////////////////////////////////////

module nic_top #(
    // Debug: bypass scrambler (TX) and descrambler (RX) - payload passes through
    // unchanged so the wire is human-readable. Headers still propagate normally.
    parameter int SCRAMBLER_BYPASS   = 0,
    parameter int DESCRAMBLER_BYPASS = 0
) (
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


`ifdef SIM_NO_PCIE
    // Sim shortcut: bypass PCIe/XDMA. Provide tied-off versions of axi_aclk and
    // axi_aresetn so the rest of the design (rx_fifo_ctrl, tx_subsystem) still works.
    assign axi_aclk          = freerun_clk;
    assign axi_aresetn       = ~freerun_rst;
    assign pci_express_x8_txn = '0;
    assign pci_express_x8_txp = '0;
    assign h2c_tdata         = '0;
    assign h2c_tkeep         = '0;
    assign h2c_tvalid        = 1'b0;
    assign h2c_tlast         = 1'b0;
    assign rx_axi_stream.ready = 1'b1;  // keep RX path draining
`else
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
`endif

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
        .DIN_W              (64),
        .GOOD_COUNT         (64),
        .BAD_COUNT          (8),
        .BITSLIP_WAIT       (256),
        .DESCRAMBLER_BYPASS (DESCRAMBLER_BYPASS)
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
        .FIFO_DEPTH       (64),
        .DESC_DEPTH       (32),
        .NUM_QUEUES       (4),
        .MAX_BURST_BEATS  (256),
        .SCRAMBLER_BYPASS (SCRAMBLER_BYPASS)
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

    // ─────────────────────────────────────────────────
    // Lock-loss diagnostics (rx_usrclk domain)
    // bad_count_q: alignment_finder's running invalid-sync-header counter
    //   in LOCKED state. Resets to 0 on every valid header; reaching
    //   BAD_COUNT-1 triggers unlock. Watching this climb shows BER bursts.
    // unlock_event_cnt: monotonic count of LOCKED→SEARCH transitions.
    // Both crossed into freerun_clk by the VIO without synchronizers —
    // multi-bit reads can briefly be torn; values are eventually consistent.
    // ─────────────────────────────────────────────────
    wire [7:0] bad_count_dbg = {{(8-$bits(rx_top_inst.u_alignment_finder.bad_count_q)){1'b0}},
                                rx_top_inst.u_alignment_finder.bad_count_q};

    reg [15:0] unlock_event_cnt = 16'h0;
    reg        rx_locked_d      = 1'b0;
    always @(posedge rx_usrclk) begin
        if (rx_pcs_rst) begin
            unlock_event_cnt <= 16'h0;
            rx_locked_d      <= 1'b0;
        end else begin
            rx_locked_d <= rx_locked;
            if (rx_locked_d && !rx_locked) unlock_event_cnt <= unlock_event_cnt + 1'b1;
        end
    end

    // ─────────────────────────────────────────────────
    // ILAs for ARP-residue debug
    //
    // Two ILAs since the suspect data crosses from rx_usrclk → axi_aclk.
    //
    // Generate in Vivado IP Catalog → "ILA (Integrated Logic Analyzer)":
    //
    //   ila_rx (clock = rx_usrclk, sample depth 1024)
    //     probe0  (1):   in_valid_i
    //     probe1  (2):   header_bits_i
    //     probe2  (8):   control_byte
    //     probe3  (64):  input_data_i
    //     probe4  (1):   out_valid_o
    //     probe5  (8):   bytes_valid_o
    //     probe6  (64):  out_data_o
    //     probe7  (1):   in_frame_q
    //     probe8  (1):   drop_frame_o
    //     probe9  (1):   send_o
    //     probe10 (1):   rx_locked
    //   Suggested trigger: control_byte == 8'h78 && header_bits_i == 2'b01
    //                      && in_valid_i  (SOF_L0 arrival)
    //
    //   ila_axi (clock = axi_aclk, sample depth 1024)
    //     probe0  (256): rx_axi_stream.data
    //     probe1  (32):  rx_axi_stream.mask  (= tkeep)
    //     probe2  (1):   rx_axi_stream.valid
    //     probe3  (1):   rx_axi_stream.last
    //     probe4  (1):   rx_axi_stream.ready
    //   Suggested trigger: valid && ready && (data[31:0] != 32'hFFFF_FFFF)
    //                      — first AXI beat whose low 4 bytes aren't broadcast
    //                      MAC, i.e. the suspect residue.
    // ─────────────────────────────────────────────────
    ila_rx u_ila_rx (
        .clk     (rx_usrclk),
        .probe0  (rx_top_inst.u_ethernet_assembler.in_valid_i),
        .probe1  (rx_top_inst.u_ethernet_assembler.header_bits_i),
        .probe2  (rx_top_inst.u_ethernet_assembler.control_byte),
        .probe3  (rx_top_inst.u_ethernet_assembler.input_data_i),
        .probe4  (rx_top_inst.u_ethernet_assembler.out_valid_o),
        .probe5  (rx_top_inst.u_ethernet_assembler.bytes_valid_o),
        .probe6  (rx_top_inst.u_ethernet_assembler.out_data_o),
        .probe7  (rx_top_inst.u_ethernet_assembler.in_frame_q),
        .probe8  (rx_top_inst.u_ethernet_assembler.drop_frame_o),
        .probe9  (rx_top_inst.u_ethernet_assembler.send_o),
        .probe10 (rx_locked),
        .probe11 (rx_top_inst.bubbler_data_66),
        .probe12 (rx_top_inst.bubbler_valid_66)
    );

    ila_axi u_ila_axi (
        .clk    (axi_aclk),
        .probe0 (rx_axi_stream.data),
        .probe1 (rx_axi_stream.mask),
        .probe2 (rx_axi_stream.valid),
        .probe3 (rx_axi_stream.last),
        .probe4 (rx_axi_stream.ready)
    );

    // ila_tx: TX path debug — confirms the FPGA is actually emitting frames
    // (vs. just idle blocks) onto gt_tx_data. Trigger on
    //   probe2 == 2'b01  (CTRL_HDR sync header from pcs_generator)
    //   AND probe1[7:0] == 8'h78  (SOF_L0 block_type byte)
    // to fire when a frame's SOF reaches the GT input. If the trigger never
    // fires while the host is sending, the FPGA TX RTL is starved
    // (h2c_tvalid never asserts, or backpressure stuck).
    //
    //   ila_tx (clock = tx_usrclk, depth 1024, 6 probes)
    //     probe0 (64): gt_tx_data
    //     probe1 (64): pcs_generator.out_data_o
    //     probe2 (2):  pcs_generator.out_control_o
    //     probe3 (1):  pcs_generator.out_valid_o
    //     probe4 (1):  h2c_tvalid
    //     probe5 (1):  h2c_tready
    ila_tx u_ila_tx (
        .clk    (tx_usrclk),
        .probe0 (gt_tx_data),
        .probe1 (tx_cdc_top_inst.u_pcs_generator.out_data_o),
        .probe2 (tx_cdc_top_inst.u_pcs_generator.out_control_o),
        .probe3 (tx_cdc_top_inst.u_pcs_generator.out_valid_o),
        .probe4 (h2c_tvalid),
        .probe5 (h2c_tready)
    );

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
        .probe_in8  (bad_count_dbg),     // 8-bit: alignment_finder bad-header counter
        .probe_in9  (unlock_event_cnt),  // 16-bit: monotonic LOCKED→SEARCH count
        .probe_out0 (loopback_mode)      // 3-bit: 000=normal, 001=PCS lb, 010=PMA lb
    );

endmodule
