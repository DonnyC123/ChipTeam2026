module scrambler #(
    parameter BIT_W   = 64,
    parameter STATE_W = 58
)(
    input  logic                     clk,
    input  logic                     rst,
    input  logic [BIT_W-1:0]     _64b_i,
    input  logic                     valid_i,
    output logic [BIT_W-1:0]     _64b_o,
    output logic                     valid_o,
);

localparam TAP_1 = 19;
localparam TAP_2 = 0;

logic [BIT_W-1:0]   scrambled_d, scrambled_q;
logic [STATE_W-1:0] state_d, state_q;
logic               valid_o_d, valid_o_q;
logic               valid_state_d, valid_state_q;

always_comb begin
    scrambled_d          = '0;
    state_d              = '0;
    valid_o_d            = 1'b0;
    valid_o_state_d      = 1'b0;
    if (valid_i && valid_state_q) begin
        for (int i = 0; i < BIT_W; i++) begin
            scrambled_d[i] = _64b_i[i] ^ state_q[TAP_1] ^ state_q[TAP_2];
            state_d        = {state_q[STATE_W-2:0], (_64b_i[i] ^ state_q[TAP_1] ^ state_q[TAP_2])};
        end
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
        state_q            <= '0;
        valid_o_state_q    <= '0;
        valid_o_q          <= '0;
    end else begin
        scrambled_q        <= scrambled_d;
        state_q            <= state_d;
        valid_state_q      <= valid_state_d;
        valid_o_q          <= valid_o_d;
    end
end

assign valid_o       = valid_o_q;
assign _64b_o        = scrambled_q;

endmodule