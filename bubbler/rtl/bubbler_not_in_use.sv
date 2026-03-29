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

logic [BIT_WIDTH_OUT-1:0]          bits_remaining,
logic [$clog2(BIT_WIDTH_OUT)-1:0]  num_bits_remaining,

bubbler_unit #(
) bubbler_unit_inst (
    .clock(clock),
    .reset(reset),
    .input_64b(input_64b),
    .input_bits_remaining(bits_remaining),
    .input_num_bits_remaining(num_bits_remaining),
    .input_valid(input_valid),
    .output_66b(output_66b),
    .output_bits_remaining(bits_remaining),
    .output_num_bits_remaining(num_bits_remaining),
    .output_valid(output_valid)
)

endmodule;