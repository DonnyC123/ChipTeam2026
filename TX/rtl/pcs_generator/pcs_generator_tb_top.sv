import pcs_pkg::*;

module pcs_generator_tb_top;
    logic                 clk;
    logic                 rst;
    logic                 out_ready_i;
    logic [DATA_W-1:0]    out_data_o;
    logic [CONTROL_W-1:0] out_control_o;
    logic                 out_valid_o;

    tx_axis_if #(
        .DATA_W(DATA_W),
        .KEEP_W(NUM_BYTES)
    ) axis_slave_if ();

    assign axis_slave_if.tdest = '0;

    pcs_generator dut (
        .clk(clk),
        .rst(rst),
        .out_ready_i(out_ready_i),
        .out_data_o(out_data_o),
        .out_control_o(out_control_o),
        .out_valid_o(out_valid_o),
        .axis_slave_if(axis_slave_if)
    );
endmodule
