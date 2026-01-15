module data_pipeline #(
    parameter int                DATA_W     = 32,
    parameter int                PIPE_DEPTH = 1,
    parameter int                RST_EN     = 1,
    parameter logic [DATA_W-1:0] RST_VAL    = '0
) (
    input  logic              clk,
    input  logic              rst,
    input  logic [DATA_W-1:0] data_i,
    output logic [DATA_W-1:0] data_o
);

  generate
    if (PIPE_DEPTH >= 1) begin : gen_delay
      logic [DATA_W-1:0] data_shift_reg_q[PIPE_DEPTH];

      always_ff @(posedge clk) begin
        if (rst && RST_EN) begin

          for (int i = 0; i < PIPE_DEPTH; i++) begin
            data_shift_reg_q[i] <= RST_VAL;
          end
        end else begin

          data_shift_reg_q[0] <= data_i;
          for (int i = 1; i < PIPE_DEPTH; i++) begin
            data_shift_reg_q[i] <= data_shift_reg_q[i-1];
          end
        end
      end

      assign data_o = data_shift_reg_q[PIPE_DEPTH-1];
    end else begin : gen_no_delay
      assign data_o = data_i;
    end
  endgenerate

endmodule

