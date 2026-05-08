module ipv4_checksum #(
    parameter DATA_W = 64,  
    parameter MASK_W = DATA_W / 8
)(
    input  logic                clk,
    input  logic                rst,

    input  logic [DATA_W-1:0]   data_i,
    input  logic [MASK_W-1:0]   mask_i,
    input  logic                payload_i, 
    input  logic                ipv4_i, 
    input  logic                valid_i,
    input logic                 sof0,

    output logic                drop_o 
);

typedef enum logic [2:0] {
    IDLE, 
    ACCUMULATE, 
    VERIFY, 
    DROP
} state_t;

state_t             state_q, state_d;

logic [5:0]         ihl_bytes_q, ihl_bytes_d;
logic [5:0]         byte_cnt_q, byte_cnt_d;
logic [31:0]        acc_q, acc_d;
logic [7:0]         acc_hi_q, acc_hi_d; 
logic [7:0]         raw_byte, eff_byte;

logic               odd_byte_q, odd_byte_d;
logic               drop_d;

function automatic logic [15:0] fold_checksum(input logic [31:0] acc);
    logic [16:0] fold1, fold2;
    fold1 = acc[31:16] + acc[15:0];
    fold2 = fold1[15:0] + {15'h0, fold1[16]};
    return ~fold2[15:0];
endfunction

always_comb begin
    state_d     = state_q;
    ihl_bytes_d = ihl_bytes_q;
    byte_cnt_d  = byte_cnt_q;
    acc_d       = acc_q;
    acc_hi_d    = acc_hi_q;
    odd_byte_d  = odd_byte_q;
    drop_d      = 1'b0;

    case (state_q)
        IDLE: begin
            // NEED TO CHECK WHICH BYTE THE IHL IS DEPENDING ON. SOF
            if (valid_i && payload_i && ipv4_i) begin
                if(sof0) begin
                    // ihl_bytes_d is the last byte streamed
                    ihl_bytes_d = {data_i[59:56], 2'b00};
                end else begin
                    //ihl_bytes is the 3rd byte streamed
                    ihl_bytes_d = {data_i[19:16], 2'b00};
                end
                byte_cnt_d  = '0;
                acc_d       = '0;
                odd_byte_d  = 1'b0;
                state_d     = ACCUMULATE;
            end
        end

        ACCUMULATE: begin
            if (valid_i) begin
                for (int i = 0; i < MASK_W; i++) begin
                    if (mask_i[i] && (byte_cnt_d < ihl_bytes_q)) begin
                        raw_byte = data_i[i*8 +: 8];
                        eff_byte = ((byte_cnt_d == 6'd10) || (byte_cnt_d == 6'd11)) ? -raw_byte : raw_byte;

                        if (!odd_byte_d)
                            acc_hi_d = eff_byte;
                        else
                            acc_d    = acc_d + {acc_hi_d, eff_byte};

                        odd_byte_d = ~odd_byte_d;
                        byte_cnt_d = byte_cnt_d + 1'b1;
                    end
                end
                if(odd_byte_d) begin
                    acc_d = acc_d + acc_hi_d;
                end
                if (byte_cnt_d >= ihl_bytes_q)
                    state_d = VERIFY;
            end
        end

        VERIFY: begin
            // need to do comparison to the actual checksum value (either taht or add the negative checksum value)
            drop_d  = (fold_checksum(acc_q) != 16'h0000);
            state_d = drop_d ? DROP : IDLE;
        end

        DROP: begin
            drop_d  = 1'b1;
            state_d = IDLE;
        end
    endcase
end

always_ff @(posedge clk) begin
    if (rst) begin
        state_q     <= IDLE;
        ihl_bytes_q <= 6'd20;
        byte_cnt_q  <= '0;
        acc_q       <= '0;
        acc_hi_q    <= '0;
        odd_byte_q  <= 1'b0;
        drop_o      <= 1'b0;
    end else begin
        state_q     <= state_d;
        ihl_bytes_q <= ihl_bytes_d;
        byte_cnt_q  <= byte_cnt_d;
        acc_q       <= acc_d;
        acc_hi_q    <= acc_hi_d;
        odd_byte_q  <= odd_byte_d;
        drop_o      <= drop_d;
    end
end

endmodule