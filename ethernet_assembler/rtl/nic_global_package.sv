package nic_global_pkg;

// These are parameters from the ethernet_assembler module, used in 64b/66b
// We dont care about C's or O's
// T = terminate (ignore all bytes to the right of the T, including the T)
// D = data
localparam logic [7:0] IDLE_BLK = 8'h1E; // C0..C7
localparam logic [7:0] SOF_L0   = 8'h78; // S0 D1..D7 (start in lane0)
localparam logic [7:0] SOF_L4   = 8'h33; // C0..C3 S4 D5..D7 (start in lane4)
localparam logic [7:0] TERM_L0  = 8'h87; // T0 C1..C7
localparam logic [7:0] TERM_L1  = 8'h99; // D0 T1 C2..C7
localparam logic [7:0] TERM_L2  = 8'hAA; // D0 D1 T2 C3..C7
localparam logic [7:0] TERM_L3  = 8'hB4; // D0 D1 D2 T3 C4..C7
localparam logic [7:0] TERM_L4  = 8'hCC; // D0..D3 T4 C5..C7
localparam logic [7:0] TERM_L5  = 8'hD2; // D0..D4 T5 C6..C7
localparam logic [7:0] TERM_L6  = 8'hE1; // D0..D5 T6 C7
localparam logic [7:0] TERM_L7  = 8'hFF; // D0..D6 T7
localparam logic [7:0] OS_D6    = 8'h66; // O0 D1..D3 O4 D5..D7 (2 Ordered Set, 6 data lanes)
localparam logic [7:0] OS_D5    = 8'h55; // O0 D1..D3 O4 O5 D6..D7 (3 Ordered Set, 5 data lanes)
localparam logic [7:0] OS_D3T   = 8'h4B; // O0 D1..D3 O4 C5..C7
localparam logic [7:0] OS_D3B   = 8'h2D; // C0..C3 O4 D5..D7


localparam logic [1:0] CTRL_HDR = 2'b10;
localparam logic [1:0] DATA_HDR = 2'b01;

localparam int SIZE_BYTE = 8;

endpackage