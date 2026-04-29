module crc_checker #(
    parameter DATA_W = 64,
    parameter MASK_W = DATA_W / 8  
)(
    input  logic              clk,
    input  logic              rst,

    input  logic [DATA_W-1:0] data_i,
    input  logic [MASK_W-1:0] mask_i,
    input  logic              valid_i,
    input  logic              send_i,
    input  logic              drop_i,
    input  logic              cancel_i,

    output logic              cancel_o,

    output logic              ready_o,

    output logic [DATA_W-1:0] data_o,
    output logic [MASK_W-1:0] mask_o,
    output logic              valid_o,
    output logic              send_o,
    output logic              drop_o
);

localparam logic [31:0] CRC32_POLY    = 32'h04C11DB7;
localparam logic [31:0] CRC32_RESIDUE = 32'hC704DD7B;
localparam logic [31:0] CRC_INIT      = 32'hFFFFFFFF;

typedef enum logic [1:0] {
    S_IDLE,
    S_STREAM,
    S_CHECK,
    S_DROP
} state_e;

state_e state_q, state_d;

logic [31:0] crc_q, crc_d;

logic [DATA_W-1:0] held_data_q, held_data_d;
logic [MASK_W-1:0] held_mask_q, held_mask_d;

function automatic logic [31:0] crc32_byte(
    input logic [31:0] crc_in,
    input logic [7:0]  byte_in
);
    logic [31:0] crc;
    logic fb;

    crc = crc_in;

    for (int i = 0; i < 8; i++) begin
        fb  = crc[31] ^ byte_in[7-i];
        crc = {crc[30:0], 1'b0} ^ (fb ? CRC32_POLY : 32'h0);
    end

    return crc;
endfunction

function automatic logic [31:0] crc32_word(
    input logic [31:0] crc_in,
    input logic [DATA_W-1:0] data,
    input logic [MASK_W-1:0] mask
);
    logic [31:0] crc;
    crc = crc_in;

    for (int b = 0; b < MASK_W; b++) begin
        if (mask[b])
            crc = crc32_byte(crc, data[b*8 +: 8]);
    end

    return crc;
endfunction

always_comb begin
    state_d     = state_q;
    crc_d       = crc_q;
    held_data_d = held_data_q;
    held_mask_d = held_mask_q;

    ready_o = 1'b0;

    data_o  = held_data_q;
    mask_o  = held_mask_q;

    valid_o = 1'b0;
    send_o  = 1'b0;
    drop_o  = 1'b0;
    cancel_o = 1'b0;

    case (state_q)

        // ---------------- IDLE ----------------
        S_IDLE: begin
            ready_o = 1'b1;

            if (cancel_i) begin
                state_d = S_IDLE;

            end else if (drop_i) begin
                drop_o  = 1'b1;
                state_d = S_IDLE;

            end else if (valid_i) begin
                crc_d       = crc32_word(CRC_INIT, data_i, mask_i);
                held_data_d = data_i;
                held_mask_d = mask_i;

                valid_o = 1'b1;
                state_d = send_i ? S_CHECK : S_STREAM;
            end
        end

        // ---------------- STREAM ----------------
        S_STREAM: begin
            ready_o = 1'b1;

            if (cancel_i) begin
                state_d = S_IDLE;
                crc_d   = CRC_INIT;

            end else if (drop_i) begin
                drop_o  = 1'b1;
                state_d = S_DROP;
                crc_d   = CRC_INIT;

            end else if (valid_i) begin
                crc_d       = crc32_word(crc_q, data_i, mask_i);
                held_data_d = data_i;
                held_mask_d = mask_i;

                valid_o = 1'b1;

                if (send_i)
                    state_d = S_CHECK;
            end
        end

        // ---------------- CHECK ----------------
        S_CHECK: begin
            ready_o = 1'b0;

            // freeze behavior: DO NOT modify crc_d here
            if (crc_q == CRC32_RESIDUE) begin
                send_o  = 1'b1;
                state_d = S_IDLE;
                crc_d   = CRC_INIT;
            end else begin
                drop_o  = 1'b1;
                state_d = S_DROP;
                crc_d   = CRC_INIT;
            end
        end

        // ---------------- DROP ----------------
        S_DROP: begin
            ready_o = 1'b0;
            drop_o  = 1'b1;
            state_d = S_IDLE;
            crc_d   = CRC_INIT;
        end

        default: state_d = S_IDLE;

    endcase
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        state_q     <= S_IDLE;
        crc_q       <= CRC_INIT;
        held_data_q <= '0;
        held_mask_q <= '0;
    end else begin
        state_q     <= state_d;
        crc_q       <= crc_d;
        held_data_q <= held_data_d;
        held_mask_q <= held_mask_d;
    end
end

endmodule