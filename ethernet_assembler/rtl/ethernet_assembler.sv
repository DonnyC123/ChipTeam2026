// Ethernet 'Assembler' Planning:
// Inputs:
// - 64 bits of input_data_i
// - 2 header bits (techinally the left most 2 bits of the 66b stream)
// - an bool in_valid_i signal which indicates if input_data_i is valid
// - a 'locked_i' bool signals which indicates that we are able to process our data
// - cancel_frame_i signal coming from the fifo we are sending data to
// IF that cancel frame signal goes high at ANY time (even for 1 cycle) then we drop the current frame 
// and ignore all data untill we see another start frame signal when control is low

// Outputs:
// - A bool out_valid_o signal that indicates if any of the output bytes are valid
// - 64 bits called out_data_o (which is the input 66 minus the 2 control bits)
// - an array of 8 data_valid signals (bools) which indicate which bytes of out_data_o are valid
// - drop_frame_o just tells the collector FIFO to ignore the current frame that its collecting

// Functionaility:
// - We need to look at the control bits
// - everything comes in in network order
// - If those bits are equal to 10 this is a control payload, and we need to check the first byte of the data (bits 63:56) to decide what to do
//     - We reference the 64/66b chart to decide if this is a start/end/idle frame
//     - We set the data_valid array based on that
//     - We need a variale to track wether we are inside of a frame, that gets set/changed
// - else If those bits are == 01 this is a data frame, and if we are inside a frame, then we can set all of the data_valid signals to high

import nic_global_pkg::*;

module ethernet_assembler #(
    parameter  int DATA_IN_W  = 64,
    parameter  int DATA_OUT_W = 64,
    localparam int BYTES_OUT  = DATA_OUT_W / SIZE_BYTE
)(
    input  logic                  clk,
    input  logic                  rst,
    input  logic                  in_valid_i,
    input  logic                  locked_i,
    input  logic                  cancel_frame_i, //from fifo, tells us to stop untill we see a start
    input  logic [DATA_IN_W-1:0]  input_data_i,
    input  logic [1:0]            header_bits_i, // network order header bits are seperate

    output logic                  drop_frame_o,
    output logic                  out_valid_o,
    output logic [DATA_OUT_W-1:0] out_data_o,
    output logic [BYTES_OUT-1:0]  bytes_valid_o
);

localparam PIPE_DEPTH = 1;

logic [1:0]            header_bits;
logic [BYTES_OUT-1:0]  bytes_valid_o_d;
logic [DATA_OUT_W-1:0] out_data_o_d;
logic [SIZE_BYTE-1:0]  control_byte;
logic                  out_valid_o_d;
logic                  drop_frame_o_d;
logic                  can_read;
logic                  drop_mode_d, drop_mode_q;
logic                  in_frame_d, in_frame_q;

// Flip the BIT order within the BYTES (get rid of network order)
function automatic logic [DATA_OUT_W-1:0] bit_reverse(input logic [DATA_OUT_W-1:0] DATA_IN);
    integer byte_idx;
    integer bit_idx;
    begin
        for (byte_idx = 0; byte_idx < BYTES_OUT; byte_idx = byte_idx + 1) begin
            for (bit_idx = 0; bit_idx < 8; bit_idx = bit_idx + 1) begin
                bit_reverse[byte_idx*8 + bit_idx] = DATA_IN[byte_idx*8 + (7-bit_idx)];
            end
        end
    end
endfunction

// Our team belives the sync/control bit are in network order
assign header_bits  = {header_bits_i[0], header_bits_i[1]}; // Filp sync/control bits from network -> regular order
assign out_data_o_d = bit_reverse(input_data_i[DATA_OUT_W-1:0]);
assign can_read     = in_valid_i && locked_i && !cancel_frame_i;
assign control_byte = out_data_o_d[DATA_OUT_W-1 -: SIZE_BYTE];

always_comb begin
    // defaults
    out_valid_o_d   = '0;
    bytes_valid_o_d = '0;
    drop_frame_o_d  = '0;
    drop_mode_d     = drop_mode_q;
    in_frame_d      = in_frame_q;

    // If cancel is seen while collecting a frame, abort that frame and enter drop mode
    if (in_frame_q && cancel_frame_i) begin
        drop_frame_o_d  = 1'b1;
        in_frame_d      = 1'b0;
        bytes_valid_o_d = '0;
        drop_mode_d     = 1'b1;

    // Drop mode: ignore everything until cancel is low and a new start frame arrives
    end else if (can_read && drop_mode_q) begin
        in_frame_d      = 1'b0;
        bytes_valid_o_d = '0;

        // 
        if (!cancel_frame_i && can_read && (header_bits == CTRL_HDR)) begin
            unique case (control_byte)
                SOF_L0: begin
                    bytes_valid_o_d = 8'b0111_1111;
                    in_frame_d      = 1'b1;
                    drop_mode_d     = 1'b0;
                end
                SOF_L4: begin
                    bytes_valid_o_d = 8'b0000_0111;
                    in_frame_d      = 1'b1;
                    drop_mode_d     = 1'b0;
                end
                default: begin
                    bytes_valid_o_d = '0;
                    in_frame_d      = 1'b0;
                    drop_mode_d     = 1'b1;
                end
            endcase
        end

    // Invalid sync header or not locked while in frame.
    end else if (in_valid_i && in_frame_q && (!locked_i || (CTRL_HDR != header_bits && DATA_HDR != header_bits))) begin
        drop_frame_o_d  = 1'b1;
        in_frame_d      = 1'b0;
        bytes_valid_o_d = '0;

    end else if (can_read && !in_frame_q && (header_bits == CTRL_HDR)) begin
        unique case (control_byte)
            // Start Frame Headers
            SOF_L0: begin bytes_valid_o_d = 8'b0111_1111; in_frame_d = 1'b1; end
            SOF_L4: begin bytes_valid_o_d = 8'b0000_0111; in_frame_d = 1'b1; end

            // Even if we see stuff like double ends, it dosen't matter because we are not in a frame
            default: begin bytes_valid_o_d = 8'b0000_0000; in_frame_d = 1'b0; end
        endcase

    // Valid input, currently in-frame, and control header.
    end else if (can_read && in_frame_q && (header_bits == CTRL_HDR)) begin
        unique case (control_byte)
        
            // End Frame Headers
            TERM_L0: begin bytes_valid_o_d = 8'b0000_0000; in_frame_d = 1'b0; end
            TERM_L1: begin bytes_valid_o_d = 8'b0100_0000; in_frame_d = 1'b0; end
            TERM_L2: begin bytes_valid_o_d = 8'b0110_0000; in_frame_d = 1'b0; end
            TERM_L3: begin bytes_valid_o_d = 8'b0111_0000; in_frame_d = 1'b0; end
            TERM_L4: begin bytes_valid_o_d = 8'b0111_1000; in_frame_d = 1'b0; end
            TERM_L5: begin bytes_valid_o_d = 8'b0111_1100; in_frame_d = 1'b0; end
            TERM_L6: begin bytes_valid_o_d = 8'b0111_1110; in_frame_d = 1'b0; end
            TERM_L7: begin bytes_valid_o_d = 8'b0111_1111; in_frame_d = 1'b0; end

            // Ordered Set + Data Headers
            OS_D6:  bytes_valid_o_d = 8'b0111_0111;
            OS_D5:  bytes_valid_o_d = 8'b0111_0111;
            OS_D3T: bytes_valid_o_d = 8'b0111_0000;
            OS_D3B: bytes_valid_o_d = 8'b0000_0111;

            default: begin bytes_valid_o_d = 8'b0000_0000; in_frame_d = 1'b0; drop_frame_o_d = 1'b1; end
        endcase

    // Valid input, currently in frame and its a data header.
    end else if (can_read && (header_bits == DATA_HDR) && in_frame_q) begin
        bytes_valid_o_d = 8'b1111_1111;
    end

    out_valid_o_d = |bytes_valid_o_d;
end

// Clocked Outputs //

// drop_frame_o_d;
data_pipeline #(
    .DATA_W    (1),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (1),
    .RST_VAL   (0)
) data_pipeline_inst1 (
    .clk   (clk),
    .rst   (rst),
    .data_i(drop_frame_o_d),
    .data_o(drop_frame_o)
);

// drop_mode_d, drop_mode_q;
data_pipeline #(
    .DATA_W    (1),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (1),
    .RST_VAL   (0)
) data_pipeline_inst2 (
    .clk   (clk),
    .rst   (rst),
    .data_i(drop_mode_d),
    .data_o(drop_mode_q)
);

// in_frame_d, in_frame_q;
data_pipeline #(
    .DATA_W    (1),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (1),
    .RST_VAL   (0)
) data_pipeline_inst3 (
    .clk   (clk),
    .rst   (rst),
    .data_i(in_frame_d),
    .data_o(in_frame_q)
);

//out_valid_o_d
data_pipeline #(
    .DATA_W    (1),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (1),
    .RST_VAL   (0)
) data_pipeline_inst4 (
    .clk   (clk),
    .rst   (rst),
    .data_i(out_valid_o_d),
    .data_o(out_valid_o)
);

//out_data_o_d
data_pipeline #(
    .DATA_W    (DATA_OUT_W),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (0)
    // theres another parameter for reset value
) data_pipeline_inst5 (
    .clk   (clk),
    .rst   (rst),
    .data_i(out_data_o_d),
    .data_o(out_data_o)
);

//bytes_valid_o_d
data_pipeline #(
    .DATA_W    (BYTES_OUT),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (0)
) data_pipeline_inst6 (
    .clk   (clk),
    .rst   (rst),
    .data_i(bytes_valid_o_d),
    .data_o(bytes_valid_o)
);

// Old Clocked Outputs
// always_ff @(posedge clk) begin
//     if (rst) begin
//         drop_mode_q     <= 1'b0;
//         in_frame_q      <= 1'b0;
//         bytes_valid_o   <= 8'h00;
//         out_valid_o     <= 1'b0; 
//         drop_frame_o    <= 1'b0;
//     end else begin
//         drop_mode_q     <= drop_mode_d;
//         in_frame_q      <= in_frame_d;
//         bytes_valid_o   <= bytes_valid_o_d;
//         out_data_o      <= out_data_o_d;
//         out_valid_o     <= out_valid_o_d;
//         drop_frame_o    <= drop_frame_o_d;
//     end
// end

endmodule
