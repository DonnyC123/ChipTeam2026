// Emulates the wire between TX and RX. On reset the buffer is pre-loaded
// with OFFSET_BITS of pseudo-random garbage so the very first bits the RX
// sees are NOT real PCS data — RX must bitslip to find alignment.
//
// Each cycle:
//   1. If slip_i is high, discard 1 bit from the output side (mimics GT PMA slide)
//   2. If tx_valid_i is high, append 64 TX bits to the high end of the buffer
//   3. If buffer holds >= 64 bits, drain 64 to RX

module wire_emulator #(
    parameter int OFFSET_BITS = 17
) (
    input  logic        clk,
    input  logic        rst,

    input  logic [63:0] tx_data_i,
    input  logic        tx_valid_i,

    output logic [63:0] rx_data_o,
    output logic        rx_valid_o,

    input  logic        slip_i
);

    localparam logic [255:0] GARBAGE_SEED =
        256'h0123_4567_89AB_CDEF_FEDC_BA98_7654_3210_DEAD_BEEF_CAFE_BABE_0F0F_F0F0_AAAA_5555;

    logic [255:0] buffer_q;
    logic [8:0]   count_q;

    logic [255:0] buffer_n;
    logic [8:0]   count_n;

    always_comb begin
        buffer_n = buffer_q;
        count_n  = count_q;
        rx_data_o  = 64'h0;
        rx_valid_o = 1'b0;

        if (slip_i && (count_n != 0)) begin
            buffer_n = buffer_n >> 1;
            count_n  = count_n - 9'd1;
        end

        if (tx_valid_i) begin
            buffer_n = buffer_n | (256'(tx_data_i) << count_n);
            count_n  = count_n + 9'd64;
        end

        if (count_n >= 9'd64) begin
            rx_data_o  = buffer_n[63:0];
            rx_valid_o = 1'b1;
            buffer_n   = buffer_n >> 64;
            count_n    = count_n - 9'd64;
        end
    end

    always_ff @(posedge clk) begin
        if (rst) begin
            buffer_q <= GARBAGE_SEED;
            count_q  <= 9'(OFFSET_BITS);
        end else begin
            buffer_q <= buffer_n;
            count_q  <= count_n;
        end
    end

endmodule
