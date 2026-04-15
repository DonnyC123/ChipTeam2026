//   Need to check if there is a manditory gap between packets
//   IMPORTANT: We are reciving 8 bytes of data, but we can only use 7 of those if we are starting a frame 
//              because we do 1 byte of data header type + 7 bytes of data and we  use <= 7 when ending a frame
//              That means that we need a buffer to hold that extra byte, and we need to use that byte in the
//              chunk. (we need an assembly buffer)
//   1. Data comes from TX -> skid buffer
//   1.1 Skid buffer holds data, byte_valid_mask, last_byte, etc.
//   2. Skid buffer -> assembly buffer, read from assembly bufferk
//   3.1 If we are not already in a frame, and we have valid data, send a start_frame & then 
//       find/append the correct data header type
//   3.2 If we are in a frame and we have valid data, then just append the correct data header type
//   3.3 If we are in frame and we see last = 1, then we make the data we see into an end frame
//   3.3 If we are not in a frame then we need to constantly send IDLE chunks
//   This can easily be a FSM
//   Idk the endian-ness that the data comes out the DMA as, that shouldn't matter
//   We also need to put the data in network order before we send it out

//   IDLE:
//      emit IDLE blocks when no frame is available
//      if frame data is available, emit a START block immediately
//      if that same block is also the last block, handle that case too if needed
//   DATA:
//      emit data blocks while payload remains
//      when last is reached, emit the proper terminate block
//      then go back to IDLE
//     
//   There is a minimum IPG of 12 bytes between a an 'end' -> next 'start'
//   We could run and 'Deficit Idle Count' which only cares that adverage IPG is 12
//   - After 1st Frame, insert 2 idle chunks (16 bytes) (4 extra)
//   - After 2nd Frame, insert 1 idle chunk (8 bytes)  (4 fewer)
//   - Adverage = 12 byte gap

///  Alternitivly we can use the SOF_L4 block which makes things a little, more complicated, but
//  then we only have to output 1 IDLE  (8 bytes) and then use the SOF_L4 which includes 4 'idle' bytes
// 
//  The minimum ethernet frame = 64 bytes so don't have to worry about start->end back to back
//  We need to wait (stall) until we have enough bytes to form a valid next block (annoying)

import pcs_pkg::*;

module pcs_generator #() 
(
    input logic clk,
    input logic rst,
    
    input logic [DATA_W-1:0]    in_data_i,
    input logic [NUM_BYTES-1:0] valid_bytes_mask_i,
    input logic                 last_byte_i,
    input logic                 valid_data_i, //the data we are seeing is valid
    input logic                 out_ready_i, //scrambler is ready to get data

    output logic                 ready_o, //we can get data from FIFO
    output logic [DATA_W-1:0]    out_data_o,
    output logic [CONTROL_W-1:0] out_control_o, //header bits
    output logic                 out_valid_o
);

//TODO: Cleanup the file, put some stuff in packages
//TODO: implement the ready_o functionality with out_ready_i backpropigation
//TODO: Finish the FSM
//TODO: talk to michael abotu the bit mask 
// Answer: we always start from the right and go left
//TODO: Verify that we actually need to put the data in network order
//TODO: Figure out the packed struct ordering, might not even need to be a packed struct.

typedef struct packed { // I don't think there is every a reason to store 8 bytes, max = 7
    logic [BYTE_W-1:0] byte0; //63-56
    logic [BYTE_W-1:0] byte1;
    logic [BYTE_W-1:0] byte2;
    logic [BYTE_W-1:0] byte3;
    logic [BYTE_W-1:0] byte4;
    logic [BYTE_W-1:0] byte5;
    logic [BYTE_W-1:0] byte6;
} leftover_bytes_t;

localparam LEFTOVER_T_W = $bits(leftover_bytes_t);


// Skid buffer is used to absorb one data when downstream cannot accept data.
// struct stores all related fields together so data/mask/last stay aligned.
typedef struct packed {
    logic [DATA_W-1:0]    data;
    logic [NUM_BYTES-1:0] valid_bytes_mask;
    logic                 last_byte;
    logic                 valid_data_i;
} skid_entry_t; 

skid_entry_t              skid_value_q;
skid_entry_t              skid_value_d;

leftover_bytes_t          leftover_bytes_q;
leftover_bytes_t          leftover_bytes_d;

typedef enum logic [2:0] {WAIT_START, DATA, IDLE_OUT} state_t;
state_t current_state, next_state;

logic       can_read;
logic       skid_valid_d, skid_valid_q; //To tell us the skid buffer has valid data
logic [2:0] held_byte_cnt_d, held_byte_cnt_q; //max count = 7

// Clocked outputs
logic                 ready_d;
logic [CONTROL_W-1:0] out_control_d;
logic [DATA_W-1:0]    out_data_d;
logic                 out_valid_d;
 
assign can_read = valid_data_i && out_ready_i;

// Always pack the inputs into the struct
always_comb begin
    skid_value_d.data             = to_network_order(in_data_i); //we will put the data in network order here
    skid_value_d.valid_bytes_mask = valid_bytes_mask_i;
    skid_value_d.last_byte        = last_byte_i;
    skid_wr_en                    = valid_data_i && ready_o;
end

// FSM combinational block
always_comb begin
    // defaults
    next_state       = current_state;
    out_valid_d      = 1'b0;
    out_data_d       = out_data_o;
    out_control_d    = out_control_o;
    held_byte_cnt_d  = held_byte_cnt_q;
    leftover_bytes_d = leftover_bytes_q;

    case(current_state) 
        WAIT_START : begin //TODO: double check this state
            //should never be in a situation where you want to start but can’t because you don’t have enough data.
            if(can_read)begin
                // Output a start chunk (SOF_L4 =  1 type + 4 idle + 3 Data)
                // This also assumes that the byte mask = '1 on a start of frame
                next_state       = DATA;
                out_control_d    = CTRL_HDR;
                out_data_d       = {SOF_L4, skid_value_d.data[DATA_W-1 -: BYTE_W*3]}; //send out 3 data bytes
                leftover_bytes_d = {skid_value_d.data[LEFTOVER_T_W-1 -: (BYTE_W*5)], '0}; //hold the other 5
                held_byte_cnt_d  = 3'd5;
                out_valid_d      = 1'b1;
            end else begin
                // Output an IDLE chunk
                out_control_d = CTRL_HDR;
                out_data_d    = {IDLE_BLK, '0}; // not 100% sure this is proper syntax
                out_valid_d   = 1'b1;
            end
        end

        DATA : begin //TODO: Finish this state
            if(can_read && !last_byte_i) begin
                // output data chunk
                // 1. figure out how many leftover & incoming
                // 2. use as many as the leftover as possible
                // 3. update the leftovers
                out_control_d = DATA_HDR;
                // TODO: ts might synthesise into some nuts LUT usage since held_byte_cnt_q is a variable, idk how to fix that tho
                out_data_d  = {leftover_bytes_q[LEFTOVER_T_W-1 -: (BYTE_W*held_byte_cnt_q)] , skid_value_d.data[DATA_W-1 -: BYTE_W*3]}; // not 100% sure this is proper syntax
                out_valid_d = 1'b1;
                
            end else if(can_read && last_byte_i) begin
                // output an end frame chunk
                // 1. figure out how many leftover & incoming
                // 2. Use that to figure out what eof block type
                // 3. check about sending one more data frame
                // 4. output the eof
                // 5. go to the IDLE_OUT state

            end
        end

        IDLE_OUT : begin // TODO: double check this state
            next_state = WAIT_START;
            // Output an IDLE chunk
            out_control_d = CTRL_HDR;
            out_data_d    = {IDLE_BLK, '0}; // not 100% sure this is proper syntax
            out_valid_d   = 1'b1;

        end
        
        default : begin
            next_state = WAIT_START;
        end
    endcase
end 

// Clocked Block
always_ff@(posedge clk)begin
    if(rst)begin
        current_state   <= WAIT_START;
        ready_o         <= '0;
        out_valid_o     <= '0;
        held_byte_cnt_q <= '0;
    end else begin
        current_state    <= next_state;
        skid_value_q     <= skid_value_d;
        ready_o          <= ready_d;
        held_byte_cnt_q  <= held_byte_cnt_d;
        out_control_o    <= out_control_d;
        out_data_o       <= out_data_d;
        out_valid_o      <= out_valid_d;
        leftover_bytes_q <= leftover_bytes_d;
    end
end

endmodule: pcs_generator