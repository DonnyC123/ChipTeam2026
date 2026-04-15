package pcs_pkg;

// These are parameters from the ethernet_assembler module, used in 64b/66b
localparam logic [7:0] IDLE_BLK = 8'h1E; // C0..C7
localparam logic [7:0] SOF_L0   = 8'h78; // S0 D1..D7 (start in lane0)
localparam logic [7:0] SOF_L4   = 8'h33; // C0..C3 S4 D5..D7 (start in lane4)

localparam logic [7:0] TERM_L0 = 8'h87; // T0 C1..C7
localparam logic [7:0] TERM_L1 = 8'h99; // D0 T1 C2..C7
localparam logic [7:0] TERM_L2 = 8'hAA; // D0 D1 T2 C3..C7
localparam logic [7:0] TERM_L3 = 8'hB4; // D0 D1 D2 T3 C4..C7
localparam logic [7:0] TERM_L4 = 8'hCC; // D0..D3 T4 C5..C7
localparam logic [7:0] TERM_L5 = 8'hD2; // D0..D4 T5 C6..C7
localparam logic [7:0] TERM_L6 = 8'hE1; // D0..D5 T6 C7
localparam logic [7:0] TERM_L7 = 8'hFF; // D0..D6 T7
localparam logic [7:0] OS_D6   = 8'h66; // O0 D1..D3 O4 D5..D7 (2 Ordered Set, 6 data lanes)
localparam logic [7:0] OS_D5   = 8'h55; // O0 D1..D3 O4 O5 D6..D7 (3 Ordered Set, 5 data lanes)
localparam logic [7:0] OS_D3T  = 8'h4B; // O0 D1..D3 O4 C5..C7
localparam logic [7:0] OS_D3B  = 8'h2D; // C0..C3 O4 D5..D7

localparam logic [1:0] CTRL_HDR = 2'b10; // 10 is in network order
localparam logic [1:0] DATA_HDR = 2'b01; // 01 is network order

localparam int BYTE_W    = 8;
localparam int CONTROL_W = 2;
localparam int NUM_BYTES = 8; 

// function automatic logic [DATA_W-1:0] to_network_order(input logic [DATA_W-1:0] DATA_IN);
//     integer byte_idx;
//     integer bit_idx;
//     localparam BYTES_OUT = DATA_W / NUM_BYTES;
//     begin
//         for (byte_idx = 0; byte_idx < BYTES_OUT; byte_idx = byte_idx + 1) begin
//             for (bit_idx = 0; bit_idx < 8; bit_idx = bit_idx + 1) begin
//                 bit_reverse[byte_idx*8 + bit_idx] = DATA_IN[byte_idx*8 + (7-bit_idx)];
//             end
//         end
//     end
// endfunction

endpackage