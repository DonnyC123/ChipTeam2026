package multiplier_pkg;
  typedef enum logic {
    READY_FOR_INPUT,
    BUSY_MULT
  } alu_state_t;

  localparam int PIPE_HIGH_LOW_SUM_LEN  = 1;
  localparam int PIPE_MULT_SUM_LEN      = 1;
  localparam int PIPE_HIGH_LOW_MULT_LEN = PIPE_HIGH_LOW_SUM_LEN + PIPE_MULT_SUM_LEN;
  localparam int PIPE_VALID_PROD_LEN    = PIPE_HIGH_LOW_MULT_LEN;
  parameter int OUT_PIPE_LEN            = 1;
endpackage

