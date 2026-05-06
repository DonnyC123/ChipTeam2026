module scrambler #(
    parameter BIT_IN_W  = 64,
    parameter BIT_OUT_W = 66,
    parameter HEAD_W    = 2,
    parameter STATE_W   = 58,
    parameter BYPASS    = 0   // 1 = pass payload through unscrambled (debug)
)(
    input  logic                     clk,
    input  logic                     rst,
    input  logic [BIT_IN_W-1:0]      _64b_i,
    input  logic                     valid_i,
    input  logic [HEAD_W-1:0]        _2b_header_i,
    output logic [BIT_OUT_W-1:0]     _66b_o,
    output logic                     valid_o
);

localparam TAP_1 = 38;
localparam TAP_2 = 57;

// Only the LFSR state is registered (it has to persist across cycles).
// The scrambled payload, header, and valid all flow through combinationally,
// so the scrambler adds zero pipeline latency.
logic [STATE_W-1:0]  state_q, state_d, state_intermediate;
logic [BIT_IN_W-1:0] scrambled;

always_comb begin
    state_d            = state_q;
    state_intermediate = state_q;
    scrambled          = '0;
    if (valid_i) begin
        for (int i = 0; i < BIT_IN_W; i++) begin
            scrambled[i]       = _64b_i[i] ^ state_intermediate[TAP_1] ^ state_intermediate[TAP_2];
            state_intermediate = {state_intermediate[STATE_W-2:0],
                                  (_64b_i[i] ^ state_intermediate[TAP_1] ^ state_intermediate[TAP_2])};
        end
        state_d = state_intermediate;
    end
end

always_ff @(posedge clk) begin
    if (rst) state_q <= '1; // MUST BE NON-ZERO (or XOR feedback freezes)
    else     state_q <= state_d;
end

assign valid_o = valid_i;
assign _66b_o  = BYPASS
    ? {_64b_i[BIT_IN_W-1:0],  _2b_header_i[HEAD_W-1:0]}
    : {scrambled[BIT_IN_W-1:0], _2b_header_i[HEAD_W-1:0]};

endmodule
