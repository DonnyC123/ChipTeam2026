module bubbler #(
    parameter BIT_IN_W   = 64,
    parameter BIT_OUT_W  = 66
)(
    input logic                              clk,
    input logic                              rst,
    input logic [BIT_IN_W-1:0]               _64b_i,
    input logic                              valid_i,
    output logic [BIT_OUT_W-1:0]             _66b_o,
    output logic                             valid_o
);

localparam BIT_OUT_COUNT_W = $clog2(BIT_OUT_W);

logic [BIT_OUT_W-1:0]           remainder_d, remainder_q;
logic [BIT_OUT_COUNT_W-1:0]     bits_remaining_d, bits_remaining_q;
logic [BIT_OUT_W-1:0]           output_d, output_q;
logic                           valid_d, valid_q;

always_comb begin
    remainder_d      = '0;
    bits_remaining_d = '0;
    output_d         = '0;
    valid_d          = '0;
    if ((bits_remaining_q + BIT_IN_W) < BIT_OUT_W || ~valid_i) begin
        remainder_d      = _64b_i;
        bits_remaining_d = BIT_IN_W;
    end else begin
        output_d         = (66'(_64b_i) << bits_remaining_q) & 66'h3FFFFFFFFFFFFFFFF;
        output_d         = output_d + remainder_q;
        remainder_d      = (66'(_64b_i) >> (BIT_IN_W - bits_remaining_q)) & 66'h3FFFFFFFFFFFFFFFF;
        bits_remaining_d = bits_remaining_q - (BIT_OUT_W - BIT_IN_W);
        valid_d          = 1'b1;
    end
end

always_ff @(posedge clk) begin
    if(rst == 1'b1)begin
        output_q         <= '0;
        remainder_q      <= '0;
        bits_remaining_q <= '0;
        valid_q          <= '0;
    end else begin
        valid_q          <= valid_d;
        bits_remaining_q <= bits_remaining_d;
        remainder_q      <= remainder_d;
        output_q         <= output_d;
    end
end

assign _66b_o  = output_q;
assign valid_o = valid_q;

endmodule