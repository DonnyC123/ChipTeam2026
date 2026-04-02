module bram #(
    parameter int BRAM_ADDR_WIDTH = 32,
    parameter int BRAM_DATA_WIDTH = 12
) (
    input  logic                            clk,
    input  logic                            ena, //enable for write
    input  logic                            enb, //enable for read
    input  logic [BRAM_ADDR_WIDTH-1:0]      addra,
    input  logic [BRAM_ADDR_WIDTH-1:0]      addrb,
    input  logic [BRAM_DATA_WIDTH-1:0]      bram_data_i,
    output logic [BRAM_DATA_WIDTH-1:0]      bram_data_o
);

    logic [BRAM_DATA_WIDTH-1:0] mem [0:(1<<BRAM_ADDR_WIDTH)-1];

    always_ff @(posedge clk) begin
        if (ena) begin
            mem[addra] <= bram_data_i;
        end
        if (enb) begin  
            bram_data_o <= mem[addrb];
        end
    end
endmodule

