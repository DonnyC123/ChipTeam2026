module crc_inserter #(
    parameter int DATA_W = 8,
    parameter int CRC_W  = 8,
    parameter logic [CRC_W-1:0] POLY = 8'h07 
) (
    input  logic                    clk,
    input  logic                    rst_n,

    input  logic                    valid_i,
    input  logic [DATA_W-1:0]       data_i,
    input  logic [DATA_W-1:0]       mask_i,

    output logic                    ready_o,
    output logic                    valid_o,
    output logic [DATA_W+CRC_W-1:0] tx_frame_o
);

    logic [CRC_W-1:0]       crc_reg;
    logic [DATA_W-1:0]      data_reg;
    logic                   busy;
    
    function automatic logic [CRC_W-1:0] calc_crc (input logic [DATA_W-1:0] data, input logic [DATA_W-1:0] mask);
        logic [CRC_W-1:0] crc;
        crc = '0;
        for (int i = DATA_W-1; i >= 0; i--) begin
            if (mask[i]) begin        
                if (crc[CRC_W-1] ^ data[i])
                    crc = (crc << 1) ^ POLY;
                else
                    crc = crc << 1;
            end
        end
        return crc;
    endfunction

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            crc_reg    <= '0;
            data_reg   <= '0;
            busy       <= 1'b0;
            valid_o    <= 1'b0;
            tx_frame_o <= '0;
        end else begin
            valid_o <= 1'b0;  

            if (valid_i && ready_o) begin
                data_reg   <= data_i;
                crc_reg    <= calc_crc(data_i, mask_i);
                busy       <= 1'b1;
            end

            if (busy) begin
                tx_frame_o <= {data_reg, crc_reg};
                valid_o    <= 1'b1;
                busy       <= 1'b0;
            end
        end
    end

    assign ready_o = !busy;

endmodule