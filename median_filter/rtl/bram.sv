module bram #(
    parameter int DATA_W = 32,
    parameter int ADDR_W = 12
) (
    input  logic              clk,
    input  logic              wr_en_i,
    input  logic [DATA_W-1:0] wr_data_i,
    input  logic [ADDR_W-1:0] wr_addr_i,
    input  logic [ADDR_W-1:0] rd_addr_i,
    output logic [DATA_W-1:0] rd_data_o
);

  localparam int BRAM_DEPTH = 2 ** ADDR_W;

  logic [DATA_W-1:0] memory[BRAM_DEPTH];

  always_ff @(posedge clk) begin
    if (wr_en_i) begin
      memory[wr_addr_i] <= wr_data_i;
    end
    rd_data_o <= memory[rd_addr_i];
  end

endmodule

