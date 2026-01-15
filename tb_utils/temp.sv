// ---------------------------------------------------------------
// Waveform
// ---------------------------------------------------------------
///
// Cycle:     0     1     2     3     4     5     6     7
//          __    __    __    __    __    __    __    __
// clk   __|  |__|  |__|  |__|  |__|  |__|  |__|  |__|  |__
//
//          _____
// start __|     |_________________________________________
//         ^ Triggers counters
//
//                     _____       _____       _____
// foo   _____________|     |_____|     |_____|     |______
//         < 2 cycles >           < +2 cyc >  < +2 cyc >
//
//                           _____             _____
// bar   ___________________|     |___________|     |______
//         <--- 3 cycles --->                 < +3 cyc >
//
// ---------------------------------------------------------------
// Description:
// Every two cycles after start_i has been asserted,
// foo_o should be asserted. Every three cycles after
// start_i has been asserted bar_o should be asserted
// ---------------------------------------------------------------
module foo_bar (
    input  logic clk,
    input  logic rst,
    input  logic start_i,
    output logic foo_o,
    output logic bar_o
);


endmodule
