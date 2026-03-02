module scrambler #(
    parameter BIT_WIDTH   = 64,
    parameter STATE_WIDTH = 58
)(
    input  logic                     clock,
    input  logic                     reset,
    input  logic [BIT_WIDTH-1:0]     input_64b,
    input  logic                     input_valid,
    output logic [BIT_WIDTH-1:0]     output_64b,
    output logic                     output_valid,
);

logic [BIT_WIDTH-1:0]   scrambled_c, scrambled_q;
logic [STATE_WIDTH-1:0] state_c, state_q;
logic                   output_valid_c, output_valid_q;
logic                   valid_state_c, valid_state_q;

always_comb begin
    scrambled_c          = '0;
    state_c              = '0;
    output_valid_c       = 1'b0;
    output_valid_state_c = 1'b0;
    if (input_valid && valid_state_q) begin
        for (int i = 0; i < 64; i++) begin
            scrambled_c[i] = input_64b[i] ^ state_q[19] ^ state_q[0];
            state_c        = {state_q[STATE_WIDTH-2:0], (input_64b[i] ^ state_q[19] ^ state_q[0])};
        end
        output_valid_c          = 1'b1;
        valid_state_c           = 1'b1;
    end else if(input_valid) begin
        output_valid_c          = 1'b0;
        valid_state_c           = 1'b1;
    end else begin
        output_valid_c          = 1'b0;
        valid_state_c           = 1'b0;
    end
end

always_ff @(posedge clock or posedge reset) begin
    if (reset == 1'b1) begin
        scrambled_q             <= '0;
        state_q                 <= '0;
        output_valid_state_q    <= '0;
        output_valid_q          <= '0;
    end else begin
        scrambled_q             <= scrambled_c;
        state_q                 <= state_c;
        valid_state_q           <= valid_state_c;
        output_valid_q          <= output_valid_c;
    end
end

assign output_valid       = output_valid_q;
assign output_64b         = scrambled_q;

endmodule