module shift_reg_en #(
    parameter int                DATA_W          = 32,
    parameter int                PIPE_DEPTH      = 2,
    parameter int                RST_EN          = 1,
    parameter logic [DATA_W-1:0] RST_VAL         = 0,
    parameter int                INCLUDE_DATA_IN = 0
) (
    input  logic              clk,
    input  logic              rst,
    input  logic              shift_en_i,
    input  logic [DATA_W-1:0] data_i,
    output logic [DATA_W-1:0] data_o    [PIPE_DEPTH]
);

  logic [DATA_W-1:0] data_shift_reg_d[PIPE_DEPTH];
  logic [DATA_W-1:0] data_shift_reg_q[PIPE_DEPTH];

  generate
    always_comb begin
      data_shift_reg_d = data_shift_reg_q;
      if (shift_en_i) begin
        data_shift_reg_d[0] = data_i;
        for (int i = 1; i < PIPE_DEPTH; i++) begin
          data_shift_reg_d[i] = data_shift_reg_q[i-1];
        end
      end
    end

    always_ff @(posedge clk) begin
      if (rst && RST_EN) begin

        for (int i = 0; i < PIPE_DEPTH; i++) begin
          data_shift_reg_q[i] <= RST_VAL;
        end
      end else begin
        data_shift_reg_q <= data_shift_reg_d;
      end
    end

    if (INCLUDE_DATA_IN) begin : gen_include_in
      assign data_o = data_shift_reg_d;
    end else begin : gen_exclude_in
      assign data_o = data_shift_reg_q;
    end
  endgenerate

endmodule

