// XSim behavioral TB: drives nic_top in PMA loopback (loopback_in = 3'b010)
// and waits for rx_locked (gpio_led[3]) to go high. Uses the gtwizard_ultrascale
// behavioral model — exercises real GT bitslip / CDR / reset behavior.
//
// To use:
//   1. In Vivado, add this file to a NEW simulation set (sim_2, etc.) so it
//      doesn't interfere with PCIe/XDMA sim (which needs vendor BFMs).
//      Or keep one sim set and accept that XDMA will boot-loop — we don't
//      care about PCIe for this test.
//   2. Set this file as the simulation top.
//   3. Set sim runtime to at least 50 us (XSim default 1 us is way too short
//      for GT reset + CDR lock + block lock).
//   4. xsim.simulate.runtime: 100us  (in project settings, or via Tcl)
//
// If you want to skip PCIe sim entirely, comment out the design_1 instance
// inside nic_top.sv before running this TB.

`timescale 1ps/1ps

module nic_top_xsim_tb;

    // 100 MHz freerun (10 ns period = 10000 ps)
    logic diff_100mhz_clk_p = 0;
    logic diff_100mhz_clk_n = 1;
    always #5000 diff_100mhz_clk_p = ~diff_100mhz_clk_p;
    always #5000 diff_100mhz_clk_n = ~diff_100mhz_clk_n;

    // 156.25 MHz GT refclk (6.4 ns period = 6400 ps)
    logic sfp_mgt_clk_p = 0;
    logic sfp_mgt_clk_n = 1;
    always #3200 sfp_mgt_clk_p = ~sfp_mgt_clk_p;
    always #3200 sfp_mgt_clk_n = ~sfp_mgt_clk_n;

    // 100 MHz PCIe refclk — design needs it present even though we ignore PCIe
    logic pcie_refclk_clk_p = 0;
    logic pcie_refclk_clk_n = 1;
    always #5000 pcie_refclk_clk_p = ~pcie_refclk_clk_p;
    always #5000 pcie_refclk_clk_n = ~pcie_refclk_clk_n;

    // SFP serial — GT internal PMA loopback handles RX, but tie off RX
    // explicitly so the GT behavioral model doesn't see X/Z on its serial input.
    logic sfp_1_rxp = 1'b0;
    logic sfp_1_rxn = 1'b1;
    wire  sfp_1_txp;
    wire  sfp_1_txn;

    // SFP control/status pins — module present, no fault, signal good
    logic sfp_1_mod_def_0 = 1'b0;
    logic sfp_1_tx_fault  = 1'b0;
    logic sfp_1_los       = 1'b0;
    wire  sfp_1_led;

    // PCIe lanes — tie off RX, leave TX floating
    logic [7:0] pci_express_x8_rxn = 8'hFF;
    logic [7:0] pci_express_x8_rxp = 8'h00;
    wire  [7:0] pci_express_x8_txn;
    wire  [7:0] pci_express_x8_txp;
    logic       pcie_perstn = 1'b0;  // hold PCIe in reset — we don't use it

    wire [3:0] gpio_led;

    nic_top u_dut (
        .diff_100mhz_clk_p (diff_100mhz_clk_p),
        .diff_100mhz_clk_n (diff_100mhz_clk_n),
        .sfp_mgt_clk_p     (sfp_mgt_clk_p),
        .sfp_mgt_clk_n     (sfp_mgt_clk_n),
        .sfp_1_rxp         (sfp_1_rxp),
        .sfp_1_rxn         (sfp_1_rxn),
        .sfp_1_txp         (sfp_1_txp),
        .sfp_1_txn         (sfp_1_txn),
        .sfp_1_mod_def_0   (sfp_1_mod_def_0),
        .sfp_1_tx_fault    (sfp_1_tx_fault),
        .sfp_1_los         (sfp_1_los),
        .sfp_1_led         (sfp_1_led),
        .pci_express_x8_rxn(pci_express_x8_rxn),
        .pci_express_x8_rxp(pci_express_x8_rxp),
        .pci_express_x8_txn(pci_express_x8_txn),
        .pci_express_x8_txp(pci_express_x8_txp),
        .pcie_perstn       (pcie_perstn),
        .pcie_refclk_clk_p (pcie_refclk_clk_p),
        .pcie_refclk_clk_n (pcie_refclk_clk_n),
        .gpio_led          (gpio_led)
    );

    // VIO probe_out0 isn't driven in sim (no JTAG). Force loopback_mode
    // continuously so the GT samples 010 (PMA loopback) at reset deassertion.
    // Use a continuous force (not a one-shot in initial) — VIO's combinational
    // driver fights us otherwise.
    always @* force u_dut.loopback_mode = 3'b010;

    // gpio_led[3] = rx_locked (direct, no CDC — see CLAUDE.md)
    wire rx_locked = gpio_led[3];

    initial begin
        $display("[%0t] sim start, waiting for rx_locked...", $time);

        // Watch for lock. GT reset sequencing alone takes microseconds.
        fork
            begin : timeout
                #100us;
                $display("[%0t] TIMEOUT — rx_locked never asserted", $time);
                $display("  freerun_rst=%b loopback_mode=%b",
                         u_dut.freerun_rst, u_dut.loopback_mode);
                $finish;
            end
            begin : success
                @(posedge rx_locked);
                $display("[%0t] rx_locked HIGH — block lock achieved", $time);
                #1us;  // settle
                $display("[%0t] sim done", $time);
                $finish;
            end
        join_any
        disable fork;
    end

    // Optional: dump waves
    initial begin
        $dumpfile("nic_top_xsim_tb.vcd");
        $dumpvars(0, nic_top_xsim_tb);
    end

endmodule
