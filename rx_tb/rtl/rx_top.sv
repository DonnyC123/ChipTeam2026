module rx_top #(
    parameter int DATA_64_W    = 64,
    parameter int DATA_66_W    = 66,
    parameter int DATA_OUT_W   = 64,
    parameter int GOOD_COUNT   = 1,
    parameter int BAD_COUNT    = 8,
    parameter int BITSLIP_WAIT = 3
)(
    input  logic                    clk,
    input  logic                    rst,

    input  logic [DATA_64_W-1:0]    raw_data_i,
    input  logic                    raw_valid_i,

    output logic                    locked_o,
    output logic                    bitslip_o,

    output logic                    out_valid_o,
    output logic [DATA_OUT_W-1:0]   out_data_o,
    output logic [DATA_OUT_W/8-1:0] bytes_valid_o
);

    logic [DATA_66_W-1:0] bubbler_data_66;
    logic                 bubbler_valid_66;

    logic [DATA_64_W-1:0] descrambled_data_64;
    logic                 descrambled_valid;

    logic[1:0]            control_o;

    logic                 drop_frame;
    logic [1:0]           header_bits_q;

    bubbler #(
        .BIT_IN_W  (DATA_64_W),
        .BIT_OUT_W (DATA_66_W)
    ) u_bubbler (
        .clk      (clk),
        .rst      (rst),
        ._64b_i   (raw_data_i),
        .valid_i  (raw_valid_i),
        ._66b_o   (bubbler_data_66),
        .valid_o  (bubbler_valid_66)
    );

    descrambler #(
        .BIT_W   (DATA_64_W),
        .STATE_W (58)
    ) u_scrambler (
        .clk      (clk),
        .rst      (rst),
        ._64b_i   (bubbler_data_66[DATA_64_W-1:0]),
        .valid_i  (bubbler_valid_66),
        ._64b_o   (descrambled_data_64),
        .valid_o  (descrambled_valid)
    );

    alignment_finder #(
        .DATA_WIDTH   (DATA_66_W),
        .GOOD_COUNT   (GOOD_COUNT),
        .BAD_COUNT    (BAD_COUNT),
        .BITSLIP_WAIT (BITSLIP_WAIT)
    ) u_alignment_finder (
        .clk          (clk),
        .rst          (rst),
        .data_valid_i (bubbler_valid_66),
        .data_i       (bubbler_data_66),
        .locked_o     (locked_o),
        .bitslip_o    (bitslip_o),
        .control_o    (control_o)
    );

    ethernet_assembler #(
        .DATA_IN_W  (DATA_64_W),
        .DATA_OUT_W (DATA_OUT_W)
    ) u_ethernet_assembler (
        .clk            (clk),
        .rst            (rst),
        .in_valid_i     (descrambled_valid),
        .locked_i       (locked_o),          
        .cancel_frame_i (1'b0),
        .input_data_i   (descrambled_data_64),
        .header_bits_i  (control_o),     
        .drop_frame_o   (drop_frame),
        .out_valid_o    (out_valid_o),
        .out_data_o     (out_data_o),
        .bytes_valid_o  (bytes_valid_o)
    );

endmodule