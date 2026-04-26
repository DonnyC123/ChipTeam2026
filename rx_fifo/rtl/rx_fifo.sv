// TODO Features:
// collect in 64b data chunks & masks
// collect 4 of those and append into 256b data chunks
// append the 4 masks as well.

// If the fifo ever stalls in any way then we need to assert the 'drop' = 1 (aka cancel_o)
// cancel_o needs to go to the DMA too because we might have given it some data that it already stored.
// drop_frame_i is from assembler, means clear the frame we are collecting.
// TODO: establish if we would ever collect 2 frames at one time
// if so then we need to know which is which for drop purposes

// TODO: figure out how the rx fifo interacts with the DMA, I'm guessing, just over the AXI if, but idk about clock part

module rx_fifo #(
    parameter FIFO_DATA_WIDTH  = 64,
    parameter FIFO_BUFFER_SIZE = 4) 
(
    //Special
    //TODO: figure out how clocks works with the DMA (cross clock domains?)
    input  logic reset,
    input  logic wr_clk_i,
    input  logic rd_clk_i,
    input  logic drop_frame_i,
    output logic cancel_o, //This is basically our drop output signal

    //Write signals
    input logic                       in_valid_i, //input data is valid
    input logic [FIFO_DATA_WIDTH-1:0] din_i,

    // Read signals
    rx_axis_if.master                  axis_if
);

//TODO: logic. Reference the fifo.sv file from 387??

endmodule : rx_fifo