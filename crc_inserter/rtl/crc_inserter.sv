module crc_inserter #(
    parameter DATA_W = 64, 
    parameter MASK_W = DATA_W / 8  
) (
    input  logic              clk,
    input  logic              rst,

    input  logic [DATA_W-1:0] data_i,
    input  logic [MASK_W-1:0] mask_i, 
    input  logic              valid_i,
    input  logic              last_i, 

    output logic              ready_o,  

    output logic [DATA_W-1:0] data_o,
    output logic [MASK_W-1:0] mask_o,
    output logic              valid_o,
    output logic              last_o   
);

localparam logic [31:0] CRC32_POLY = 32'h04C11DB7;
localparam logic [31:0] CRC_INIT   = 32'hFFFFFFFF;
localparam logic [31:0] CRC_XOR    = 32'hFFFFFFFF;  

typedef enum logic [1:0] {
    S_IDLE, 
    S_STREAM, 
    S_APPEND, 
    S_TAIL   
} state_e;

state_e state_q, state_d;

function automatic logic [31:0] crc32_byte(
    input logic [31:0] crc_in,
    input logic [7:0]  byte_in
);
    logic [31:0] crc;
    logic        fb;
    crc = crc_in;
    for (int i = 0; i < 8; i++) begin
        fb  = crc[31] ^ byte_in[7-i];
        crc = {crc[30:0], 1'b0} ^ (fb ? CRC32_POLY : 32'h0);
    end
    return crc;
endfunction

function automatic logic [31:0] crc32_word(
    input logic [31:0]        crc_in,
    input logic [DATA_W-1:0]  data,
    input logic [MASK_W-1:0]  mask
);
    logic [31:0] crc;
    crc = crc_in;
    for (int b = 0; b < MASK_W; b++)
        if (mask[b])
            crc = crc32_byte(crc, data[b*8 +: 8]);
    return crc;
endfunction

logic [31:0]       crc_q;       
logic [31:0]       crc_d;  
logic [DATA_W-1:0] held_data_q;
logic [DATA_W-1:0] held_data_d; 
logic [MASK_W-1:0] held_mask_q; 
logic [MASK_W-1:0] held_mask_d;
logic [2:0]        free_bytes_q;
logic [2:0]        free_bytes_d; 

logic [DATA_W-1:0] data_d;
logic [MASK_W-1:0] mask_d;
logic              last_d;

function automatic logic [2:0] free_slots(input logic [MASK_W-1:0] mask);
    logic [2:0] cnt;
    cnt = '0;
    for (int i = 0; i < MASK_W; i++)
        cnt += {2'b0, ~mask[i]};
    return cnt;
endfunction

logic [31:0] crc_final;   
logic [31:0] crc_next; 

assign crc_final = ~crc_q;  

always_comb begin
    state_d      = state_q;
    crc_d        = crc_q;
    held_data_d  = held_data_q;
    held_mask_d  = held_mask_q;
    free_bytes_d = free_bytes_q;

    ready_o = 1'b0;
    data_d = data_i;
    mask_d = mask_i;
    valid_o = 1'b0;
    last_o  = 1'b0;
    last_d  = 1'b0;

    crc_next = crc32_word(crc_q, data_i, mask_i);

    unique case (state_q)

        S_IDLE: begin
            ready_o = 1'b1;
            crc_d      = CRC_INIT;

            if (valid_i) begin
                crc_d        = crc32_word(CRC_INIT, data_i, mask_i);
                free_bytes_d = free_slots(mask_i);
                held_data_d  = data_i;
                held_mask_d  = mask_i;

                valid_o = 1'b1;

                state_d = S_STREAM;
            end
        end

        S_STREAM: begin
            ready_o = 1'b1;

            if (valid_i) begin
                crc_d        = crc_next;
                held_data_d  = data_i;
                held_mask_d  = mask_i;
                free_bytes_d = free_slots(mask_i);

                valid_o = 1'b1;

                if (last_i) begin
                    if (free_bytes_q >= 3'd4) begin
                        logic [DATA_W-1:0] out_data;
                        logic [MASK_W-1:0] out_mask;
                        int                slot;

                        out_data = data_i;
                        out_mask = mask_i;
                        slot     = 0;

                        for (int b = 0; b < MASK_W; b++) begin
                            if (!mask_i[b] && slot < 4) begin
                                case (slot)
                                    0: out_data[b*8 +: 8] = crc_d[31:24];
                                    1: out_data[b*8 +: 8] = crc_d[23:16];
                                    2: out_data[b*8 +: 8] = crc_d[15:8];
                                    3: out_data[b*8 +: 8] = crc_d[7:0];
                                endcase
                                out_mask[b] = 1'b1;
                                slot++;
                            end
                        end

                        data_d = out_data;
                        mask_d = out_mask;
                        last_d = 1'b1;
                        state_d = S_IDLE;
                    end else begin
                        logic [DATA_W-1:0] out_data;
                        logic [MASK_W-1:0] out_mask;
                        int                slot;

                        out_data = data_i;
                        out_mask = mask_i;
                        slot     = 0;

                        for (int b = 0; b < MASK_W; b++) begin
                            if (!mask_i[b]) begin
                                case (slot)
                                    0: out_data[b*8 +: 8] = crc_d[31:24];
                                    1: out_data[b*8 +: 8] = crc_d[23:16];
                                    2: out_data[b*8 +: 8] = crc_d[15:8];
                                    3: out_data[b*8 +: 8] = crc_d[7:0];
                                    default: ;
                                endcase
                                out_mask[b] = 1'b1;
                                slot++;
                            end
                        end

                        data_d = out_data;
                        mask_d = out_mask;
                        last_d = 1'b0;  

                        free_bytes_d = free_bytes_q;
                        state_d      = S_TAIL;
                    end
                end
            end
        end

        // S_APPEND: begin
        //     ready_o = 1'b0;
        //     valid_o = 1'b1;

        //     if (free_bytes_q >= 3'd4) begin
        //         begin
        //             logic [DATA_W-1:0] out_data;
        //             logic [MASK_W-1:0] out_mask;
        //             int                slot;

        //             out_data = held_data_q;
        //             out_mask = held_mask_q;
        //             slot     = 0;

        //             for (int b = 0; b < MASK_W; b++) begin
        //                 if (!held_mask_q[b] && slot < 4) begin
        //                     case (slot)
        //                         0: out_data[b*8 +: 8] = crc_final[31:24];
        //                         1: out_data[b*8 +: 8] = crc_final[23:16];
        //                         2: out_data[b*8 +: 8] = crc_final[15:8];
        //                         3: out_data[b*8 +: 8] = crc_final[7:0];
        //                         default: ;
        //                     endcase
        //                     out_mask[b] = 1'b1;
        //                     slot++;
        //                 end
        //             end

        //             data_o = out_data;
        //             mask_o = out_mask;
        //             last_o = 1'b1;
        //         end
        //         state_d = S_IDLE;

        //     end else begin
        //         begin
        //             logic [DATA_W-1:0] out_data;
        //             logic [MASK_W-1:0] out_mask;
        //             int                slot;
        //             out_data = held_data_q;
        //             out_mask = held_mask_q;
        //             slot     = 0;

        //             for (int b = 0; b < MASK_W; b++) begin
        //                 if (!held_mask_q[b]) begin
        //                     case (slot)
        //                         0: out_data[b*8 +: 8] = crc_final[31:24];
        //                         1: out_data[b*8 +: 8] = crc_final[23:16];
        //                         2: out_data[b*8 +: 8] = crc_final[15:8];
        //                         3: out_data[b*8 +: 8] = crc_final[7:0];
        //                         default: ;
        //                     endcase
        //                     out_mask[b] = 1'b1;
        //                     slot++;
        //                 end
        //             end

        //             data_o = out_data;
        //             mask_o = out_mask;
        //             last_o = 1'b0;  
        //         end

        //         free_bytes_d = free_bytes_q;
        //         state_d      = S_TAIL;
        //     end
        // end

        S_TAIL: begin
            logic [DATA_W-1:0] out_data;
            logic [MASK_W-1:0] out_mask;
            int                remaining;
            int                sent;

            ready_o = 1'b0;
            valid_o = 1'b1;
            last_o  = 1'b1;

            out_data  = '0;
            out_mask  = '0;
            sent      = int'(free_bytes_q); 
            remaining = 4 - sent;

            for (int b = 0; b < remaining; b++) begin
                case (sent + b)
                    0: out_data[b*8 +: 8] = crc_q[31:24];
                    1: out_data[b*8 +: 8] = crc_q[23:16];
                    2: out_data[b*8 +: 8] = crc_q[15:8];
                    3: out_data[b*8 +: 8] = crc_q[7:0];
                endcase
                out_mask[b] = 1'b1;
            end

            data_d = out_data;
            mask_d = out_mask;

            state_d = S_IDLE;
        end
    endcase
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        state_q      <= S_IDLE;
        crc_q        <= CRC_INIT;
        held_data_q  <= '0;
        held_mask_q  <= '0;
        free_bytes_q <= '0;
    end else begin
        data_o       <= data_d;
        mask_o       <= mask_d;
        state_q      <= state_d;
        crc_q        <= crc_d;
        held_data_q  <= held_data_d;
        held_mask_q  <= held_mask_d;
        free_bytes_q <= free_bytes_d;
    end
end

endmodule