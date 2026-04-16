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

/// Alternitivly we can use the SOF_L4 block which makes things a little, more complicated, but
//  then we only have to output 1 IDLE  (8 bytes) and then use the SOF_L4 which includes 4 'idle' bytes
//  The C lanes after T do count toward the interpacket gap
// Have constmts depending on 

import pcs_pkg::*;

module pcs_generator #() 
(
    input  logic                 clk,
    input  logic                 rst,
    input  logic                 out_ready_i, //scrambler is ready to get data
    output logic [DATA_W-1:0]    out_data_o,
    output logic [CONTROL_W-1:0] out_control_o, //header bits
    output logic                 out_valid_o,

    tx_axis_if.slave              axis_slave_if
);

//TODO: Cleanup the file, put some stuff in packages
//TODO: implement the ready_o functionality with out_ready_i backpropigation
//TODO: Finish the FSM

//bit mask always starts from the right and go left

typedef struct packed { // We would only ever store 5 bytes
    logic [BYTE_W-1:0] byte0 //31-33
    logic [BYTE_W-1:0] byte1
    logic [BYTE_W-1:0] byte2
    logic [BYTE_W-1:0] byte3
    logic [BYTE_W-1:0] byte4 //0-7
} leftover_bytes_t;

function automatic logic [3:0] count_valid (input logic[BYTE_W-1:0] mask);
    unique casez (mask)
        8'b???????0: count_valid = 0;
        8'b??????01: count_valid = 1;
        8'b?????011: count_valid = 2;
        8'b????0111: count_valid = 3;
        8'b???01111: count_valid = 4;
        8'b??011111: count_valid = 5;
        8'b?0111111: count_valid = 6;
        8'b01111111: count_valid = 7;
        8'b11111111: count_valid = 8;
        default:     count_valid = 0;
    endcase
endfunction

// Skid buffer is used to absorb one chunk of data when downstream cannot accept an output
typedef struct packed {
    logic [DATA_W-1:0]    data;
    logic [NUM_BYTES-1:0] valid_bytes_mask;
    logic                 last_byte;
    logic                 valid_data_i;
} skid_entry_t; 

localparam LEFTOVER_T_W = $bits(leftover_bytes_t);


skid_entry_t              skid_value_q;
skid_entry_t              skid_value_d;

leftover_bytes_t          leftover_bytes_q;
leftover_bytes_t          leftover_bytes_d;


typedef enum logic [3:0] {WAIT_START, DATA, EOF, IDLE_OUT} state_t;
state_t current_state, next_state;

logic       can_read;
logic       next_is_last;
logic       skid_valid_d, skid_valid_q; //To tell us the skid buffer has valid data
logic [2:0] held_byte_cnt_d, held_byte_cnt_q; //max count = 7
logic [3:0] num_incoming_d, num_incoming_q;

// Clocked port outputs
logic                 ready_d;
logic [CONTROL_W-1:0] out_control_d;
logic [DATA_W-1:0]    out_data_d;
logic                 out_valid_d;
 
// FSM traversal Flags
assign can_read     = skid_value_q.valid_data_i  && out_ready_i;
assign next_is_last = axis_slave_if.valid_data_i && axis_slave_if.tlast; //means that the thing in the skid buffer is the eof signal

// Always pack the inputs into the struct
// TODO: Check that this is correct, we might only want to grab data on tready, maybe we alwyas grab but we only clock it on tready
always_comb begin
    skid_value_d.data             = in_data_i; //we will put the data in network order here
    skid_value_d.valid_bytes_mask = valid_bytes_mask_i;
    skid_value_d.last_byte        = last_byte_i;
    skid_value_d.valid_data_i     = valid_data_i;
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
    num_incoming_d   = num_incoming_q;

    case(current_state) 
        WAIT_START : begin 
            if(can_read)begin
                next_state    = DATA;
                out_control_d = CTRL_HDR;

                // always grab 5 to hold, dosen't matter if we don't use them all
                leftover_bytes_d = {skid_value_q.data[DATA_W-1 -: (5*BYTE_W)]};

                if(CONDITION) begin //TODO decide condition, should just be a flag? seperate state?? 
                // bsically we want held_byte_cnt_q = some value (5 or 1), which we can set except for intial boot
                    // Output a start chunk (SOF_L4 =  3 Data + 4 IDLE + 1 type)
                    out_data_d      = {skid_value_q.data[(3*BYTE_W)-1:0], 4{BYTE_W'd0}, SOF_L4}; //send out 3 data bytes
                    held_byte_cnt_d = 3'd5;
                end else begin // Output a start chunk (SOF_L0=  7 data + 1 type)
                    out_data_d      = {skid_value_q.data[(7*BYTE_W)-1:0], SOF_L0}; //send out 7 data bytes
                    held_byte_cnt_d = 3'd1;
                end
                out_valid_d = 1'b1;

            end else begin // Output an IDLE chunk
                out_control_d = CTRL_HDR;
                out_data_d    = {7{8'd0}, IDLE_BLK};
                out_valid_d   = 1'b1;
            end
        end
        
        DATA : begin
            if(can_read) begin
                leftover_bytes_d = {skid_value_q.data[DATA_W-1 -: (5*BYTE_W)]}; // always grab 5, even if not used

                if(held_byte_cnt_q == 3'd5) begin //the num of bytes stored will never change as long as valid_mask = '1
                    out_data_d = {skid_value_q.data[(BYTE_W*3)-1:0], leftover_bytes_q};
                end else begin 
                    out_data_d = {skid_value_q.data[(BYTE_W*7)-1:0], leftover_bytes_q[LEFTOVER_T_W -: BYTE_W]};
                end

                out_valid_d = 1'b1; 
            end

            // if data in skid buffer has the eof signal, go to the EOF state, and pre-compute num of valid incoming bytes
            if(can_read && next_is_last) begin
                next_state     = EOF;
                num_incoming_d = count_valid(skid_value_q);
            end
        end

        //TODO: fix this state. We basiclally need one case statement for when we are holding 5 and one case statemnet for when we are holding 1
        EOF : begin
            if(can_read) begin
                if(num_incoming_q + held_byte_cnt_q < 7) begin // We can output all the data
                if(held_byte_cnt_q == 3'b5) begin
                    // this cases pulls all 5 held then, in should be between 0-2
                end else begin
                    // this case pulls 1 and then in should be between 0-6
                    // need to catch the case where we sent out all the data, and have 0 to send out.

                end
                    case(num_incoming_q)
                        3'd0 : out_data_d = {{7{BYTE_W'd0}}, TERM_L0};
            
                        3'd1 : out_data_d = {{6{BYTE_W'd0}}, leftover_bytes_q[LEFTOVER_T_W -: BYTE_W], TERM_L1};
            
                        3'd2 : out_data_d = {{5{BYTE_W'd0}}, leftover_bytes_q[LEFTOVER_T_W -: BYTE_W*2], TERM_L2};
            
                        3'd3 : out_data_d = {{4{BYTE_W'd0}}, leftover_bytes_q[LEFTOVER_T_W -: BYTE_W*3], TERM_L3};
            
                        3'd4 : out_data_d = {{3{BYTE_W'd0}}, leftover_bytes_q[LEFTOVER_T_W -: BYTE_W*4], TERM_L4};
            
                        3'd5 : out_data_d = {{2{BYTE_W'd0}}, leftover_bytes_q[LEFTOVER_T_W -: BYTE_W*5], TERM_L5};
            
                        3'd6 : out_data_d = {{1{BYTE_W'd0}}, leftover_bytes_q[LEFTOVER_T_W -: BYTE_W*6], TERM_L6};
            
                        3'd7 : out_data_d = {leftover_bytes_q, TERM_L7};
                    endcase
                    out_valid_d     = 1'b1;
                    held_byte_cnt_q = 3'd0;
                end else begin // if num_incoming_q + held_byte_cnt_q > 7, we need to output another data packet before flushing

                    num_incoming_d   = num_incoming_q - (8-held_byte_cnt_q); //calculate num left after sending this data chunk
                    leftover_bytes_d = skid_value_q.data[(7*BYTE_W)-1:0]; // at max we would have 5 leftover (5 stored, + 8 incoming, 8 go out this cycle) 

                    if(held_byte_cnt_q == 3'd5) begin
                        out_data_d = {skid_value_q.data[(BYTE_W*3)-1:0], leftover_bytes_q[(5*BYTE_W)-1:0]};
                    end else begin 
                        out_data_d = {skid_value_q.data[(BYTE_W*7)-1:0], leftover_bytes_q[BYTE_W-1:0]};
                    end

                    out_valid_d = 1'b1;
                end
            end
        end

        IDLE_OUT : begin // TODO: Add an indicator/logic for what start frame to output (lowkey could just use held_byte_cnt_q/d)
            next_state = WAIT_START;
            // Output an IDLE chunk
            out_control_d = CTRL_HDR;
            out_data_d    = {7{BYTE_W'd0}, IDLE_BLK};
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
        num_incoming_q  <= '0
    end else begin
        current_state    <= next_state;
        skid_value_q     <= skid_value_d;
        ready_o          <= ready_d;
        held_byte_cnt_q  <= held_byte_cnt_d;
        out_control_o    <= out_control_d;
        out_data_o       <= out_data_d;
        out_valid_o      <= out_valid_d;
        leftover_bytes_q <= leftover_bytes_d;
        num_incoming_q   <= num_incoming_d;
    end
end

endmodule: pcs_generator