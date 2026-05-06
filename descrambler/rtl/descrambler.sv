module descrambler #(
    parameter BIT_W   = 64,
    parameter STATE_W = 58,
    parameter BYPASS  = 0   // 1 = pass payload through undescrambled (debug)
) (
    input  logic             clk,
    input  logic             rst,
    input  logic [BIT_W-1:0] _64b_i,
    input  logic             valid_i,
    output logic [BIT_W-1:0] _64b_o,
    output logic             valid_o
);

  localparam TAP_1 = 38;
  localparam TAP_2 = 57;

  logic [BIT_W-1:0] descrambled_d, descrambled_q;
  logic [STATE_W-1:0] state_d, state_q, state_intermediate;
  logic valid_o_d, valid_o_q;
  logic valid_state_d, valid_state_q;

  always_comb begin
    descrambled_d = '0;
    state_d       = state_q;  // HOLD by default, don't clobber
    valid_o_d     = 1'b0;
    valid_state_d = valid_state_q;  // also hold this

    if (valid_i && valid_state_q) begin
      state_intermediate = state_q;
      for (int i = 0; i < BIT_W; i++) begin
        descrambled_d[i]   = _64b_i[i] ^ state_intermediate[TAP_1] ^ state_intermediate[TAP_2];
        state_intermediate = {state_intermediate[STATE_W-2:0], _64b_i[i]};
      end
      state_d       = state_intermediate;
      valid_o_d     = 1'b1;
      valid_state_d = 1'b1;
    end else if (valid_i) begin
      state_intermediate = state_q;
      for (int i = 0; i < BIT_W; i++) begin
        state_intermediate = {state_intermediate[STATE_W-2:0], _64b_i[i]};
      end
      state_d       = state_intermediate;
      valid_o_d     = 1'b0;
      valid_state_d = 1'b1;
    end
  end

  always_ff @(posedge clk) begin
    if (rst == 1'b1) begin
      descrambled_q <= '0;
      state_q       <= '1;
      valid_state_q <= '0;
      valid_o_q     <= '0;
    end else begin
      descrambled_q <= descrambled_d;
      state_q       <= state_d;
      valid_state_q <= valid_state_d;
      valid_o_q     <= valid_o_d;
    end
  end

  logic [BIT_W-1:0] payload_q;
  always_ff @(posedge clk) begin
    if (rst) payload_q <= '0;
    else if (valid_i) payload_q <= _64b_i;
  end

  assign valid_o = valid_o_q;
  assign _64b_o  = BYPASS ? payload_q : descrambled_q;



endmodule

