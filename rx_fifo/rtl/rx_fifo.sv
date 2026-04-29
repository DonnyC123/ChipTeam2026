// TODO Features:
// collect in 64b data chunks & masks
// collect 4 of those and append into 256b data chunks
// append the 4 masks as well.

// If the fifo ever stalls in any way then we need to assert the 'drop' = 1 (aka cancel_o)
// cancel_o needs to go to the DMA too because we might have given it some data that it already stored.
// drop_frame_i is from assembler, means clear the frame we are collecting.
// TODO: establish if we would ever collect 2 frames at one time
// if so then we need to know which is which for drop purposes

//TODO: figure out how clocks works with the DMA (cross clock domains?)
import rx_fifo_pkg::*;

module rx_fifo #(
    parameter FIFO_DATA_WIDTH  = 64,
    parameter FIFO_BUFFER_SIZE = 4) 
(
    //Special
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

//TODO: logic. Reference the fifo.sv file from 387
//TODO: This does synchronous clock domain crossing.
//TODO: We need to make the read/write pointers grey coded to make it ascynchronous clock domain crossing

localparam FIFO_ADDR_WIDTH = $clog2(FIFO_BUFFER_SIZE) + 1;
logic [FIFO_DATA_WIDTH-1:0] fifo_buf [FIFO_BUFFER_SIZE-1:0];
//TODO: need different versions for grey and the bin widths
logic [FIFO_ADDR_WIDTH-1:0] wr_addr, wr_addr_t;
logic [FIFO_ADDR_WIDTH-1:0] rd_addr, rd_addr_t;
logic                       full_t, empty_t;

always_ff @(posedge wr_clk) 
begin : p_write_buffer
    if ( (wr_en == 1'b1) && (full_t == 1'b0) ) begin
        fifo_buf[$unsigned(wr_addr[FIFO_ADDR_WIDTH-2:0])] <= din; //TODO: din = former port
    end
end

//TODO: wr_addr needs to be greycoded here, binary when doing full checks
always_ff @(posedge wr_clk, posedge reset) 
begin : p_wr_addr
    if ( reset == 1'b1 ) 
        wr_addr <= '0;
    else
        wr_addr <= wr_addr_t;
end

//TODO: 'dout' is formally a port signal, now in bundle
always_ff @(posedge rd_clk) 
begin : p_rd_buffer
    dout <= to01(fifo_buf[$unsigned(rd_addr_t[FIFO_ADDR_WIDTH-2:0])]);
end

//TODO: 'rd_addr' is formally a port signal, now in bundle
always_ff @(posedge rd_clk, posedge reset) 
begin : p_rd_addr
    if ( reset == 1'b1 ) 
        rd_addr <= '0;
    else
        rd_addr <= rd_addr_t;
end

//TODO: 'empty' is formally a port signal, now in bundle
always_ff @(posedge rd_clk, posedge reset) 
begin : p_empty
    if ( reset == 1'b1 ) 
        empty <= '1;
    else
        empty <= (wr_addr == rd_addr_t) ? 1'b1 : 1'b0;
end

assign rd_addr_t = (rd_en == 1'b1 && empty_t == 1'b0) ? ($unsigned(rd_addr) + 'h1) : rd_addr;
assign wr_addr_t = (wr_en == 1'b1 && full_t == 1'b0) ? ($unsigned(wr_addr) + 'h1) : wr_addr;

assign empty_t = (wr_addr == rd_addr) ? 1'b1 : 1'b0;

// TODO: wr_addr and rd_addr will be gray, this full check won't work, needs binary, indexing would be off too.
assign full_t = (wr_addr[FIFO_ADDR_WIDTH-2:0] == rd_addr[FIFO_ADDR_WIDTH-2:0]) &&
                (wr_addr[FIFO_ADDR_WIDTH-1] != rd_addr[FIFO_ADDR_WIDTH-1]) ? 1'b1 : 1'b0;
assign full = full_t;




endmodule : rx_fifo