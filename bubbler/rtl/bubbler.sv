module bubbler #(
    parameter BIT_IN_W  = 64,
    parameter BIT_OUT_W = 66
) (
    input  logic                 clk,
    input  logic                 rst,
    input  logic [ BIT_IN_W-1:0] _64b_i,
    input  logic                 valid_i,
    output logic [BIT_OUT_W-1:0] _66b_o,
    output logic                 valid_o
);

  // Buffer wide enough to hold leftover (up to BIT_IN_W bits) plus a fresh input beat.
  localparam int SHIFT_REG_W = BIT_IN_W + BIT_OUT_W;        // 130 bits
  localparam int COUNT_W     = $clog2(SHIFT_REG_W + 1);     // bits-buffered counter

  logic [SHIFT_REG_W-1:0] shift_reg;
  logic [SHIFT_REG_W-1:0] remainder_d, remainder_q;
  logic [    COUNT_W-1:0] bits_remaining_d, bits_remaining_q;
  logic [  BIT_OUT_W-1:0] output_d, output_q;
  logic                   valid_out_d, valid_out_q;

  // Pack new 64-bit input above whatever leftover is already buffered (at LSB).
  // Result: bits [bits_remaining_q-1:0] = leftover, bits [bits_remaining_q+63:bits_remaining_q] = new.
  assign shift_reg = remainder_q | (SHIFT_REG_W'(_64b_i) << bits_remaining_q);

  always_comb begin
    output_d         = output_q;
    valid_out_d      = 1'b0;
    remainder_d      = remainder_q;
    bits_remaining_d = bits_remaining_q;

    if (!valid_i) begin
      // Reset accumulator on invalid — caller has to re-feed two valid beats before output.
      remainder_d      = '0;
      bits_remaining_d = '0;
    end else if (bits_remaining_q + BIT_IN_W >= BIT_OUT_W) begin
      // Have enough bits to emit. Output is the bottom 66 bits; carry the rest forward.
      output_d         = shift_reg[BIT_OUT_W-1:0];
      remainder_d      = shift_reg >> BIT_OUT_W;
      bits_remaining_d = bits_remaining_q + BIT_IN_W - BIT_OUT_W;
      valid_out_d      = 1'b1;
    end else begin
      // First valid beat after reset/invalid drop — accumulate, no output yet.
      remainder_d      = shift_reg;
      bits_remaining_d = bits_remaining_q + BIT_IN_W;
    end
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      output_q         <= '0;
      remainder_q      <= '0;
      bits_remaining_q <= '0;
      valid_out_q      <= '0;
    end else begin
      output_q         <= output_d;
      remainder_q      <= remainder_d;
      bits_remaining_q <= bits_remaining_d;
      valid_out_q      <= valid_out_d;
    end
  end

  assign _66b_o  = output_q;
  assign valid_o = valid_out_q;

endmodule
