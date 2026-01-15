module interview #(
    parameter int DATA_W = 8
) (
    input  logic              clk,
    input  logic              rst,
    input  logic [DATA_W-1:0] data_i,
    input  logic              data_valid_i,
    output logic [DATA_W-1:0] data_o,
    output logic              data_valid_o
);

  always_ff @(posedge clk) begin
    if (rst) begin
      data_valid_o <= '0;
    end else begin
      data_o       <= data_i;
      data_valid_o <= data_valid_i;
    end
  end
endmodule
