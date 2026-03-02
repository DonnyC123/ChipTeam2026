module scrambler #(
    parameter BIT_WIDTH   = 64,
    parameter STATE_WIDTH = 58
)(
    input  logic                     clock,
    input  logic                     reset,
    input  logic [BIT_WIDTH-1:0]     input_64b,
    input  logic                     input_valid,
    output logic [BIT_WIDTH-1:0]     output_64b,
    output logic                     output_valid
);

logic [STATE_WIDTH-1:0]   state;
logic                     state_valid;

scrambler_unit #(
) scrambler_unit_inst (
    .clock(clock),
    .reset(reset),
    .input_64b(input_64b),
    .input_valid(input_valid),
    .input_state(state),
    .input_state_valid(state_valid),
    .output_64b(output_64b),
    .output_valid(output_valid),
    .output_state(state),
    .output_state_valid(state_valid)
)

endmodule