module bubbler #(
    parameter BIT_WIDTH_IN   = 64,
    parameter BIT_WIDTH_OUT  = 66
)(
    input logic                              clock,
    input logic                              reset,
    input logic [BIT_WIDTH_IN-1:0]           input_64b,
    input logic                              input_valid,
    output logic [BIT_WIDTH_OUT-1:0]         output_66b,
    output logic                             output_valid
);

logic [BIT_WIDTH_OUT-1:0]           remainder_c, remainder_q;
logic [$clog2(BIT_WIDTH_OUT)-1:0]   bits_remaining_c, bits_remaining_q;
logic [BIT_WIDTH_OUT-1:0]           output_c, output_q;
logic                               valid_c, valid_q;

always_comb begin
    remainder_c      = '0;
    bits_remaining_c = '0;
    output_c         = '0;
    valid_c          = '0;
    if ((bits_remaining_q + 64) < 66 || ~input_valid) begin
        remainder_c      = input_64b;
        bits_remaining_c = 64;
    end else begin
        output_c         = (input_64b << bits_remaining_q) & 66'h3FFFFFFFFFFFFFFFF;
        output_c         = output_c + remainder_q;
        remainder_c      = (input_64b >> (64 - bits_remaining_q)) & 66'h3FFFFFFFFFFFFFFFF;
        bits_remaining_c = bits_remaining_q - 2;
        valid_c = 1'b1;
    end
end

always_ff @(posedge clock or posedge reset) begin
    if(reset == 1'b1)begin
        output_q         <= '0;
        remainder_q      <= '0;
        bits_remaining_q <= '0;
        valid_q          <= '0;
    end else begin
        valid_q          <= valid_c;
        bits_remaining_q <= bits_remaining_c;
        remainder_c      <= remainder_c;
        output_c         <= output_c;
    end
end

assign output_66b                   = output_q;
assign output_bits_remaining        = remainder_q;
assign output_num_bits_remaining    = bits_remaining_q;
assign output_valid                 = valid_q;

endmodule