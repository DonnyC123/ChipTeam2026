module debubbler #(
    parameter BIT_IN_W   = 66,
    parameter BIT_OUT_W  = 64
)(
    input logic                              clk,
    input logic                              rst,
    input logic [BIT_IN_W-1:0]               _66b_i,
    input logic                              valid_i,
    output logic [BIT_OUT_W-1:0]             _64b_o,
    output logic                             valid_o,
    output logic                             ready_o
);

localparam BIT_OUT_COUNT_W = $clog2(BIT_IN_W);
localparam READY_STOP_THRESHOLD = BIT_OUT_W - (2 * (BIT_IN_W - BIT_OUT_W));

logic [BIT_OUT_W-1:0]           remainder_d, remainder_q;
logic [BIT_OUT_COUNT_W-1:0]     bits_remaining_d, bits_remaining_q;
logic [BIT_OUT_W-1:0]           output_d, output_q;
logic                           valid_d, valid_q;
logic                           ready_d, ready_q;

always_comb begin
    output_d         = output_q;
    remainder_d      = remainder_q;
    bits_remaining_d = bits_remaining_q;
    valid_d          = 1'b0;
    ready_d          = 1'b1;
    if(bits_remaining_q == 64) begin
        output_d         = remainder_q;
        remainder_d      = '0;
        bits_remaining_d = '0;
        ready_d          = '0;
        valid_d          = '1;
    end else if(valid_i) begin
        output_d         = remainder_q | 64'(_66b_i << bits_remaining_q);
        remainder_d      = 64'(_66b_i >> (BIT_OUT_W-bits_remaining_q));
        bits_remaining_d = bits_remaining_q + (BIT_IN_W - BIT_OUT_W);
        valid_d          = 1'b1;
    end
end

always_ff @(posedge clk) begin
    if(rst == 1'b1)begin
        output_q         <= '0;
        remainder_q      <= '0;
        bits_remaining_q <= '0;
        valid_q          <= '0;
        ready_q          <= '0;
    end else begin
        ready_q          <= ready_d;
        valid_q          <= valid_d;
        bits_remaining_q <= bits_remaining_d;
        remainder_q      <= remainder_d;
        output_q         <= output_d;
    end
end

//Assign outputs
assign _64b_o  = output_q;
assign valid_o = valid_q;
assign ready_o = ready_d && (bits_remaining_q < READY_STOP_THRESHOLD);

//For testing ONLY
always_ff @(posedge clk) begin
    if(valid_i) begin
        $display("time=%0t | DeBUBBLER | 66i=%02h | 64o=%02h",
                 $time, _66b_i, _64b_o);
    end
end

endmodule
