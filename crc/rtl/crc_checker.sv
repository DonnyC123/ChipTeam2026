module crc_checker #(
    parameter int DATA_W = 8,
    parameter int CRC_W  = 8,
    parameter logic [CRC_W-1:0] POLY = 8'h07 
) (
    input  logic                        clk,
    input  logic                        rst_n,

    input  logic                        valid_i,
    input  logic [DATA_W+CRC_W-1:0]     rx_frame_i,
    input logic [DATA_W-1:0]            mask_i,    

    output logic                        ready_o,
    output logic                        valid_o,
    output logic [DATA_W-1:0]           data_o,
    output logic                        crc_valid_o
);

    logic [DATA_W-1:0]  data_reg;
    logic [CRC_W-1:0]   rx_crc_reg;
    logic [DATA_W-1:0]  mask_reg;
    logic               busy;

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
            data_reg    <= '0;
            rx_crc_reg  <= '0;
            busy        <= '0;
            valid_o     <= '0;
            data_o      <= '0;
            crc_valid_o <= '0;
        end else begin
            valid_o <= '0; 

            if (valid_i && ready_o) begin
                data_reg   <= rx_frame_i[DATA_W+CRC_W-1 : CRC_W];
                rx_crc_reg <= rx_frame_i[CRC_W-1 : 0];
                mask_reg   <= mask_i;
                busy       <= 1'b1;
            end

            if (busy) begin
                automatic logic [CRC_W-1:0] computed;
                computed   = calc_crc(data_reg, mask_reg);
                crc_valid_o <= (computed == rx_crc_reg);
                data_o     <= data_reg;
                valid_o    <= 1'b1;
                busy       <= 1'b0;
            end
        end
    end

    assign ready_o = !busy;

endmodule