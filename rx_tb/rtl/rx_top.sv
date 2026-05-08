import parser_pkg::*;

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

    output logic                    checksum_drop_o,
    output logic                    parser_valid_o
);

    logic [DATA_66_W-1:0] bubbler_data_66;
    logic                 bubbler_valid_66;

    logic [DATA_64_W-1:0] descrambled_data_64;
    logic                 descrambled_valid;

    logic                 drop_frame;
    logic [1:0]           header_bits_q;

    // parser signals
    outputs_t             parser_outputs;
    logic                 parser_valid;
    logic                 parser_payload;
    logic                 parser_sof_type;

    // alignment_finder outputs — were undeclared (implicit 1-bit)
    logic                 locked_o;
    logic                 bitslip_o;

    // ethernet_assembler outputs — were undeclared (implicit 1-bit)
    logic                 out_valid_o;
    logic [DATA_OUT_W-1:0] out_data_o;
    logic [DATA_OUT_W/8-1:0] bytes_valid_o;  // 8-bit byte-enable mas

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
        .bitslip_o    (bitslip_o)
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
        .header_bits_i  (header_bits_q),     
        .drop_frame_o   (drop_frame),
        .out_valid_o    (out_valid_o),
        .out_data_o     (out_data_o),
        .bytes_valid_o  (bytes_valid_o)
    );

    ethernet_parser #(
        .DATA_IN_W (DATA_OUT_W)
    ) u_ethernet_parser (
        .clk            (clk),
        .rst            (rst),

        .data_valid_i   (out_valid_o),
        .data_i         (out_data_o),
        .bytes_valid_i  (bytes_valid_o),

        .sof_type_o     (parser_sof_type),
        .payload_time_o (parser_payload),
        .valid_o        (parser_valid_o),
        .outputs_o      (parser_outputs)
    );

    ip_checksum #(
        .DATA_W (DATA_OUT_W)
    ) u_ip_checksum (
        .clk       (clk),
        .rst       (rst),

        .data_i    (out_data_o),
        .mask_i    (bytes_valid_o),
        .valid_i   (out_valid_o),

        .payload_i (parser_payload),
        .ipv4_i    (parser_outputs == IPV4),
        .sof0      (parser_sof_type),

        .drop_o    (checksum_drop_o)
    );

    always_ff @(posedge clk) begin
        if (rst) begin
            header_bits_q <= '0;
        end else begin
            header_bits_q <= bubbler_data_66[65:64];
        end
    end

endmodule