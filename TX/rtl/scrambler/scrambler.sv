module scrambler #(
    parameter BIT_IN_W  = 64,
    parameter BIT_OUT_W = 66,
    parameter HEAD_W    = 2,
    parameter STATE_W   = 58
)(
    input  logic                     clk,
    input  logic                     rst,
    input  logic [BIT_IN_W-1:0]      _64b_i,
    input  logic                     valid_i,
    input  logic [HEAD_W-1:0]        _2b_header_i,
    output logic [BIT_OUT_W-1:0]     _66b_o,
    output logic                     valid_o
);

localparam TAP_1 = 19;
localparam TAP_2 = 0;

logic [BIT_IN_W-1:0] scrambled_d, scrambled_q;
logic [STATE_W-1:0]  state_d, state_q, state_intermediate;
logic                valid_o_d, valid_o_q;
logic                valid_state_d, valid_state_q;
logic [HEAD_W-1:0]   header_prop_d, header_prop_q;

always_comb begin
    scrambled_d          = '0;
    state_d              = '1;
    valid_o_d            = 1'b0;
    valid_state_d        = 1'b0;
    header_prop_d        = _2b_header_i;
    if (valid_i && valid_state_q) begin
        state_intermediate = state_q;
        for (int i = 0; i < BIT_IN_W; i++) begin
            scrambled_d[i]     = _64b_i[i] ^ state_intermediate[TAP_1] ^ state_intermediate[TAP_2];
            state_intermediate = {state_intermediate[STATE_W-2:0], (_64b_i[i] ^ state_intermediate[TAP_1] ^ state_intermediate[TAP_2])};
        end
        state_d = state_intermediate;
        valid_o_d          = 1'b1;
        valid_state_d      = 1'b1;
    end else if(valid_i) begin
        valid_o_d          = 1'b0;
        valid_state_d      = 1'b1;
    end else begin
        valid_o_d          = 1'b0;
        valid_state_d      = 1'b0;
    end
end

always_ff @(posedge clk) begin
    if (rst == 1'b1) begin
        scrambled_q        <= '0;
        state_q            <= '1; // MUST BE NON-ZERO (OR XOR WILL FREEZE)
        valid_state_q      <= '0;
        valid_o_q          <= '0;
        header_prop_q      <= '0;
    end else begin
        scrambled_q        <= scrambled_d;
        state_q            <= state_d;
        valid_state_q      <= valid_state_d;
        valid_o_q          <= valid_o_d;
        header_prop_q      <= header_prop_d;
    end
end

assign valid_o       = valid_o_q;
assign _66b_o        = {header_prop_q[HEAD_W-1:0], scrambled_q[BIT_IN_W-1:0]};

endmodule