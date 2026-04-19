//   We are reciving 8 bytes of data, when SOF or DATA, but can't output all of them so need a storage buffer
//   1. Data comes from TX -> skid buffer (needed for backpressure)
//   1.1 Skid buffer holds data, byte_valid_mask, last_byte, etc.
//   2. Skid buffer -> assembly buffer, read from assembly buffer 
//   3.1 If we are not already in a frame, and we have valid data, send a start_frame & then 
//       find/append the correct data header type
//   3.2 If we are in a frame and we have valid data, then just append the correct data header type
//   3.3 If we are in frame and we see last = 1, then we make the data we see into an end frame, might need to output 1 more data chunk
//   3.3 If we are not in a frame then we need to constantly send IDLE chunks
//     
//   There is a minimum IPG of 12 bytes between a an 'end' -> next 'start'
//   The C lanes after T do count toward the interpacket gap

import pcs_pkg::*;

module pcs_generator #() 
(
    input  logic                 clk,
    input  logic                 rst,
    input  logic                 out_ready_i, //scrambler is ready to get data
    output logic [DATA_W-1:0]    out_data_o,
    output logic [CONTROL_W-1:0] out_control_o, //header bits
    output logic                 out_valid_o,

    tx_axis_if.slave             axis_slave_if
);

skid_entry_t              skid_value_q;
skid_entry_t              skid_value_d;

leftover_bytes_t          leftover_bytes_q;
leftover_bytes_t          leftover_bytes_d;


typedef enum logic [3:0] {WAIT_START, DATA, EOF, IDLE_OUT} state_t;
state_t current_state, next_state;

logic       can_read;
logic       next_is_last;
logic [2:0] held_byte_cnt_d, held_byte_cnt_q; //max ever stored = 5
logic [3:0] num_incoming_d, num_incoming_q; //max ever incoming = 8

// Clocked port outputs
logic                 ready_d;
logic                 get_axi;
logic [CONTROL_W-1:0] out_control_d;
logic [DATA_W-1:0]    out_data_d;
logic                 out_valid_d;
logic                 tready_d;
 
// FSM traversal Flags
assign can_read     = skid_value_q.valid_data_i  && out_ready_i;
assign next_is_last = axis_slave_if.tvalid && axis_slave_if.tlast; //means that the thing in the skid buffer is the eof signal
assign get_axi      = axis_slave_if.tvalid && axis_slave_if.tready;

// Always pack the inputs into the struct
always_comb begin
    skid_value_d.data             = axis_slave_if.tdata; //we will put the data in network order here, if we switch up again
    skid_value_d.valid_bytes_mask = axis_slave_if.tkeep;
    skid_value_d.last_byte        = last_byte_i;
    skid_value_d.valid_data_i     = axis_slave_if.valid_data_i;
end

// FSM combinational block
always_comb begin
    // defaults
    next_state       = current_state;
    out_data_d       = out_data_o;
    out_control_d    = out_control_o;
    held_byte_cnt_d  = held_byte_cnt_q;
    leftover_bytes_d = leftover_bytes_q;
    num_incoming_d   = num_incoming_q;
    out_valid_d      = 1'b0;
    tready_d         = 1'b1;

    case(current_state) 
        WAIT_START : begin 
            if(can_read)begin
                next_state    = DATA;
                out_control_d = CTRL_HDR;

                // always grab 5 to hold, dosen't matter if we don't use them all
                leftover_bytes_d = {skid_value_q.data[DATA_W-1 -: (5*BYTE_W)]};

                if(held_byte_cnt_q == 3'd5) begin //
                // bsically we want held_byte_cnt_q = some value (5 or 1), which we can set except for intial boot (intial boot is the issue)
                    // Output a start chunk (SOF_L4 =  3 Data + 4 IDLE + 1 type)
                    out_data_d      = {skid_value_q.data[(3*BYTE_W)-1:0], {4{8'd0}}, SOF_L4}; //send out 3 data bytes
                    held_byte_cnt_d = 3'd5;
                end else begin // Output a start chunk (SOF_L0=  7 data + 1 type), 
                    out_data_d      = {skid_value_q.data[(7*BYTE_W)-1:0], SOF_L0}; //send out 7 data bytes
                    held_byte_cnt_d = 3'd1;
                end
                out_valid_d = 1'b1;

            end else begin // Output an IDLE chunk
                out_control_d   = CTRL_HDR;
                out_data_d      = {{7{8'd0}}, IDLE_BLK};
                out_valid_d     = 1'b1;
                held_byte_cnt_d = 1'b1;
            end
        end
        
        DATA : begin
            if(can_read) begin
                out_control_d    = DATA_HDR;
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

        EOF : begin // Frozen here we have some data in the leftover buffer, and out last data in the skid buffer.
            if(can_read) begin
                if(num_incoming_q + held_byte_cnt_q < 7) begin // We can output all the data
                    out_control_d = CTRL_HDR;
                    if(held_byte_cnt_q == 3'd5) begin // we have some data in the leftover buffer, and out last data in the skid buffer.
                        // this cases pulls all 5 held then, num_in should be between 0-2
                        case(num_incoming_q)
                            3'd0 : out_data_d = {{7{8'd0}}, TERM_L0};

                            3'd5 : out_data_d = {{2{8'd0}}, leftover_bytes_q[LEFTOVER_T_W -: BYTE_W*5], TERM_L5};
                
                            3'd6 : out_data_d = {{1{8'd0}}, skid_value_q.data[0 +: BYTE_W-1], leftover_bytes_q[LEFTOVER_T_W -: BYTE_W*5], TERM_L6};
                
                            3'd7 : out_data_d = {skid_value_q.data[0 +: (BYTE_W*2)-1], leftover_bytes_q[LEFTOVER_T_W -: BYTE_W*5], TERM_L6};
                        endcase
                    end else begin
                        // this case pulls 1 and then num_in should be between 0-6
                        // need to catch the case where we sent out all the data, and have 0 to send out.
                        case(num_incoming_q)
                            3'd0 : out_data_d = {{7{8'd0}}, TERM_L0};

                            3'd1 : out_data_d = {{6{8'd0}}, leftover_bytes_q[LEFTOVER_T_W -: BYTE_W], TERM_L1};
                
                            3'd2 : out_data_d = {{5{8'd0}}, skid_value_q.data[0 +: (BYTE_W*1)-1], leftover_bytes_q[LEFTOVER_T_W -: BYTE_W], TERM_L2};
                
                            3'd3 : out_data_d = {{4{8'd0}}, skid_value_q.data[0 +: (BYTE_W*2)-1], leftover_bytes_q[LEFTOVER_T_W -: BYTE_W], TERM_L3};
                
                            3'd4 : out_data_d = {{3{8'd0}}, skid_value_q.data[0 +: (BYTE_W*3)-1], leftover_bytes_q[LEFTOVER_T_W -: BYTE_W], TERM_L4};
                
                            3'd5 : out_data_d = {{2{8'd0}}, skid_value_q.data[0 +: (BYTE_W*4)-1], leftover_bytes_q[LEFTOVER_T_W -: BYTE_W], TERM_L5};
                
                            3'd6 : out_data_d = {{1{8'd0}}, skid_value_q.data[0 +: (BYTE_W*5)-1], leftover_bytes_q[LEFTOVER_T_W -: BYTE_W], TERM_L6};
                
                            3'd7 : out_data_d = {skid_value_q.data[0 +: (BYTE_W*6)-1],  leftover_bytes_q[LEFTOVER_T_W -: BYTE_W], TERM_L7};
                        endcase

                    end

                    out_valid_d     = 1'b1;
                    held_byte_cnt_q = 3'd0;
                end else begin // if num_incoming_q + held_byte_cnt_q > 7, we need to output another data packet before flushing
                    out_control_d    = DATA_HDR;
                    tready_d         = 1'b0; //We don't need another AXI beat right now since we are forcing a data_frame
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

        IDLE_OUT : begin
            next_state = WAIT_START;
            // Output an IDLE chunk
            out_control_d    = CTRL_HDR;
            out_data_d       = {{7{8'd0}}, IDLE_BLK};
            out_valid_d      = 1'b1;
            leftover_bytes_q = (get_axi) ?  3'd5 : 3'd1; //if data right away need SOF_L4, else SOF_L0
        end
        
        default : begin
            next_state = WAIT_START;
        end
    endcase
end 

// Clocked Block
// TODO: convert these to use the pipeline module
always_ff@(posedge clk)begin
    if(rst)begin
        current_state        <= WAIT_START;
        axis_slave_if.tready <= '0;
        out_valid_o          <= '0;
        held_byte_cnt_q      <= '0;
        num_incoming_q       <= '0;
    end else begin
        current_state <= next_state;
        if(get_axi == 1'b1) begin
            skid_value_q <= skid_value_d;
        end
        axis_slave_if.tready <= ready_d;
        held_byte_cnt_q      <= held_byte_cnt_d;
        out_control_o        <= out_control_d;
        out_data_o           <= out_data_d;
        out_valid_o          <= out_valid_d;
        leftover_bytes_q     <= leftover_bytes_d;
        num_incoming_q       <= num_incoming_d;
    end
end

endmodule: pcs_generator