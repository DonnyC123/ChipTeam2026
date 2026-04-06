module alu
  import alu_pkg::*;
#(
    parameter int DIN_W  = 8,
    parameter int DOUT_W = 2 * DIN_W
) (
    input logic                clk,
    input logic                rst,
    input logic    [DIN_W-1:0] a_operand_i,
    input logic    [DIN_W-1:0] b_operand_i,
    input opcode_t             opcode_i,
    input logic                op_valid_i,

    output logic [DOUT_W-1:0] data_o,
    output logic              data_valid
);

  typedef enum logic {
    ADD,
    MULT
  } opcode_t;

  typedef enum logic {
    READY_FOR_INPUT,
    BUSY_MULT
  } alu_state_t;

  localparam int HALF_W = (DIN_W + 1) / 2;

  localparam int HIGH_LOW_SUM_W = HALF_W + 1;
  localparam int PARTIAL_MULT_W = 2 * HALF_W + 1;

  localparam int PIPE_HIGH_LOW_SUM_LEN = 1;
  localparam int PIPE_HIGH_LOW_MULT_LEN = 1 + PIPE_HIGH_LOW_SUM_LEN;

  logic [HALF_W-1:0] a_low;
  logic [HALF_W-1:0] a_high;
  logic [HALF_W-1:0] b_low;
  logic [HALF_W-1:0] b_high;

  logic [HIGH_LOW_SUM_W-1:0] a_sum_d;
  logic [HIGH_LOW_SUM_W-1:0] a_sum_q;
  logic [HIGH_LOW_SUM_W-1:0] b_sum_d;
  logic [HIGH_LOW_SUM_W-1:0] b_sum_q;

  logic [2*HALF_W-1:0] partial_mult_low_d;
  logic [2*HALF_W-1:0] partial_mult_low_q;
  logic [2*HALF_W-1:0] partial_mult_high_d;
  logic [2*HALF_W-1:0] partial_mult_high_q;

  logic [2*HALF_W+1:0] partial_mult_sum_d;
  logic [2*HALF_W+1:0] partial_mult_sum_q;

  logic [2*HALF_W+1:0] mid_term;

  always_comb begin
    a_low               = a_operand_i[HALF_W-1:0];
    a_high              = a_operand_i[DIN_W-1:HALF_W];
    b_low               = b_operand_i[HALF_W-1:0];
    b_high              = b_operand_i[DIN_W-1:HALF_W];

    a_sum_d             = a_low + a_high;
    b_sum_d             = b_low + b_high;

    partial_mult_low_d  = a_low * b_low;
    partial_mult_high_d = a_high * b_high;
  end

  data_pipeline #(
      .DATA_W    (2 * HIGH_LOW_SUM_W),
      .PIPE_DEPTH(PIPE_HIGH_LOW_SUM_LEN),
      .RST_EN    (0)
  ) data_pipeline_high_low_sum (
      .clk   (clk),
      .rst   (rst),
      .data_i({a_sum_d, b_sum_d}),
      .data_o({a_sum_q, b_sum_q})
  );

  data_pipeline #(
      .DATA_W    (2 * HIGH_LOW_SUM_W),
      .PIPE_DEPTH(PIPE_HIGH_LOW_SUM_LEN),
      .RST_EN    (0)
  ) data_pipeline_high_low_sum (
      .clk   (clk),
      .rst   (rst),
      .data_i({partial_mult_low_d, partial_mult_high_d}),
      .data_o({partial_mult_low_q, partial_mult_high_q})
  );

  always_comb begin
  end

  assign partial_mult_sum_d = a_sum_q * b_sum_q;

  always_comb begin
    mid_term = partial_mult_sum_q - partial_mult_low_q - partial_mult_high_q;
    p_out = (partial_mult_high_q << DIN_W) + (mid_term << HALF_W) + partial_mult_low_q;
  end

endmodule
