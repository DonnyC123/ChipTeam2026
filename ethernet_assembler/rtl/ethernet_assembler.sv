// Ethernet 'Assembler' Planning:
// Inputs:
// - 64 bits of input_data_i
// - 2 header bits (the first 2 bits of each 66b block on the wire, IEEE 802.3 Clause 49)
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


//IMPORTANT UPDATE network order is not a real thing.

// IPG counting uses TERM tail bytes, IDLE_BLK bytes, and SOF_L4 lead-in bytes.

import nic_global_pkg::*;

module ethernet_assembler #(
    parameter  int DATA_IN_W  = 64,
    parameter  int DATA_OUT_W = 64,
    localparam int BYTES_OUT  = DATA_OUT_W / SIZE_BYTE
)(
    input logic                 clk,
    input logic                 rst,
    input logic                 in_valid_i,
    input logic                 locked_i,
    input logic                 cancel_frame_i, //from fifo, tells us to stop untill we see a start
    input logic [DATA_IN_W-1:0] input_data_i,
    input logic [1:0]           header_bits_i, //network order header bits are seperate

    output logic                  send_o, //entire frame is good
    output logic                  drop_frame_o,
    output logic                  out_valid_o,
    output logic [DATA_OUT_W-1:0] out_data_o,
    output logic [BYTES_OUT-1:0]  bytes_valid_o
);

localparam PIPE_DEPTH = 1;

logic [BYTES_OUT-1:0]  bytes_valid_o_d;
logic [DATA_OUT_W-1:0] out_data_o_d;
logic [SIZE_BYTE-1:0]  control_byte;
logic [IPG_BIT_W-1:0]  ipg_counter_d, ipg_counter_q;
logic                  ipg_check_en_d, ipg_check_en_q;
logic                  out_valid_o_d;
logic                  drop_frame_o_d;
logic                  can_read;
logic                  send_d;
logic                  drop_mode_d, drop_mode_q;
logic                  in_frame_d, in_frame_q;
logic                  sof_l4_first_data_d, sof_l4_first_data_q;
// Sticky flag: 1 throughout an SOF_L4 frame (set on SOF_L4, cleared on
// TERM/cancel/drop). Used to keep emitted AXI tkeep contiguous by realigning
// the half-block-shifted MAC bytes — the upper 4 bytes (lanes 4-7) of each
// DATA block are buffered and combined with the next block's lower 4 bytes
// (lanes 0-3) for emission. Without this, the first DATA block of an SOF_L4
// frame would emit with mask 0xF0 (non-contiguous) which XDMA C2H Stream
// handles inconsistently.
logic                  sof_l4_active_d,     sof_l4_active_q;
logic [31:0]           sof_l4_buf_d,        sof_l4_buf_q;


// Our team belives the sync/control bit are in network order
assign can_read     = in_valid_i && locked_i && !cancel_frame_i;
assign control_byte = input_data_i[0 +: SIZE_BYTE]; // the data_type_byte is bits [7:0] of data

// Output data path. In SOF_L4 mode, repack to keep AXI tkeep contiguous.
// - DATA2..DATAn  : emit {incoming lanes 0-3, buffered prev lanes 4-7}.
// - TERM_L0..L4   : emit {TERM data lanes (1..x), buffered lanes 4-7} so
//                   trailing bytes are right-aligned to lanes 0..3+x.
// Outside SOF_L4 mode, pass through unchanged (legacy SOF_L0 path).
always_comb begin
    out_data_o_d = input_data_i;
    if (sof_l4_active_q && in_frame_q
            && (header_bits_i == DATA_HDR) && !sof_l4_first_data_q) begin
        // DATA2+ in SOF_L4: realign half-block-shifted MAC bytes.
        out_data_o_d = {input_data_i[31:0], sof_l4_buf_q};
    end else if (sof_l4_active_q && in_frame_q
            && (header_bits_i == CTRL_HDR)) begin
        unique case (control_byte)
            TERM_L0: out_data_o_d = {32'h0,                 sof_l4_buf_q};
            TERM_L1: out_data_o_d = {24'h0, input_data_i[15:8],  sof_l4_buf_q};
            TERM_L2: out_data_o_d = {16'h0, input_data_i[23:8],  sof_l4_buf_q};
            TERM_L3: out_data_o_d = {8'h0,  input_data_i[31:8],  sof_l4_buf_q};
            TERM_L4: out_data_o_d = {input_data_i[39:8],         sof_l4_buf_q};
            default: out_data_o_d = input_data_i;
        endcase
    end
end

always_comb begin
    // defaults
    send_d              = '0;
    out_valid_o_d       = '0;
    bytes_valid_o_d     = '0;
    drop_frame_o_d      = '0;
    ipg_counter_d       = ipg_counter_q;
    ipg_check_en_d      = ipg_check_en_q;
    drop_mode_d         = drop_mode_q;
    in_frame_d          = in_frame_q;
    sof_l4_first_data_d = sof_l4_first_data_q;
    sof_l4_active_d     = sof_l4_active_q;
    sof_l4_buf_d        = sof_l4_buf_q;

    // If cancel is seen while collecting a frame, abort that frame and enter drop mode
    if (in_frame_q && cancel_frame_i) begin
        drop_frame_o_d      = 1'b1;
        in_frame_d          = 1'b0;
        bytes_valid_o_d     = '0;
        ipg_counter_d       = '0;
        drop_mode_d         = 1'b1;
        sof_l4_first_data_d = 1'b0;
        sof_l4_active_d     = 1'b0;

    // Drop mode: ignore everything until cancel is low and a new start frame arrives
    end else if (can_read && drop_mode_q) begin
        in_frame_d      = 1'b0;
        bytes_valid_o_d = '0;

        // start and exit drop mode
        if (!cancel_frame_i && can_read && (header_bits_i == CTRL_HDR)) begin
            unique case (control_byte)
                // IEEE 802.3 Cl. 49: SOF block lanes 1-7 are the trailing
                // preamble + SFD (0x55..0xd5), NOT MAC frame data. Discard
                // them — the real frame starts at lane 0 of the next block.
                SOF_L0: begin
                    if (!ipg_check_en_q || (ipg_counter_q >= IPG_MIN_BYTES)) begin
                        bytes_valid_o_d = 8'b0000_0000;
                        in_frame_d      = 1'b1;
                        ipg_counter_d   = '0;
                        ipg_check_en_d  = 1'b1;
                        drop_mode_d     = 1'b0;
                    end else begin
                        drop_frame_o_d = 1'b1;
                        in_frame_d     = 1'b0;
                        ipg_counter_d  = '0;
                        drop_mode_d    = 1'b1;
                    end
                end
                SOF_L4: begin
                    if (!ipg_check_en_q || (ipg_counter_q >= IPG_SOF_L4_BYTES)) begin
                        bytes_valid_o_d     = 8'b0000_0000;
                        in_frame_d          = 1'b1;
                        ipg_counter_d       = '0;
                        ipg_check_en_d      = 1'b1;
                        drop_mode_d         = 1'b0;
                        sof_l4_first_data_d = 1'b1;
                        sof_l4_active_d     = 1'b1;
                    end else begin
                        drop_frame_o_d = 1'b1;
                        in_frame_d     = 1'b0;
                        ipg_counter_d  = '0;
                        drop_mode_d    = 1'b1;
                    end
                end
                IDLE_BLK: begin
                    if (ipg_counter_q >= IPG_IDLE_SAT) begin
                        ipg_counter_d = IPG_MIN_BYTES;
                    end else begin
                        ipg_counter_d = ipg_counter_q + IPG_IDLE_BYTES;
                    end
                end
            endcase
        end

    // Invalid sync header or not locked while in frame.
    end else if (in_valid_i && in_frame_q && (!locked_i || (CTRL_HDR != header_bits_i && DATA_HDR != header_bits_i))) begin
        drop_frame_o_d      = 1'b1;
        in_frame_d          = 1'b0;
        bytes_valid_o_d     = '0;
        ipg_counter_d       = '0;
        drop_mode_d         = 1'b1;
        sof_l4_first_data_d = 1'b0;
        sof_l4_active_d     = 1'b0;

    end else if (can_read && !in_frame_q && (header_bits_i == CTRL_HDR)) begin
        unique case (control_byte)
            // Start Frame Headers — lanes 1-7 are preamble per IEEE Cl. 49
            // and must NOT be forwarded as MAC frame data.
            SOF_L0: begin
                if (!ipg_check_en_q || (ipg_counter_q >= IPG_MIN_BYTES)) begin
                    bytes_valid_o_d = 8'b0000_0000;
                    in_frame_d      = 1'b1;
                    ipg_counter_d   = '0;
                    ipg_check_en_d  = 1'b1;
                end else begin
                    drop_frame_o_d = 1'b1;
                    in_frame_d     = 1'b0;
                    ipg_counter_d  = '0;
                    drop_mode_d    = 1'b1;
                end
            end
            SOF_L4: begin
                if (!ipg_check_en_q || (ipg_counter_q >= IPG_SOF_L4_BYTES)) begin
                    bytes_valid_o_d     = 8'b0000_0000;
                    in_frame_d          = 1'b1;
                    ipg_counter_d       = '0;
                    ipg_check_en_d      = 1'b1;
                    sof_l4_first_data_d = 1'b1;
                    sof_l4_active_d     = 1'b1;
                end else begin
                    drop_frame_o_d = 1'b1;
                    in_frame_d     = 1'b0;
                    ipg_counter_d  = '0;
                    drop_mode_d    = 1'b1;
                end
            end

            // When out of frame, only IDLE_BLK grows the IPG byte counter.
            IDLE_BLK: begin
                if (ipg_counter_q >= IPG_IDLE_SAT) begin
                    ipg_counter_d = IPG_MIN_BYTES;
                end else begin
                    ipg_counter_d = ipg_counter_q + IPG_IDLE_BYTES;
                end
            end
        endcase

    // Valid input, currently in-frame, and control header.
    end else if (can_read && in_frame_q && (header_bits_i == CTRL_HDR)) begin
        sof_l4_first_data_d = 1'b0;
        // TERM ends the frame; in SOF_L4 mode the masks shift up by 4 bits
        // because the 4 buffered MAC bytes (from the prior DATA's lanes 4-7)
        // are emitted at lanes 0-3 of this beat alongside any TERM data.
        unique case (control_byte)

            // End Frame Headers — SOF_L0 mode masks land at lanes 1..x;
            // SOF_L4 mode masks land at lanes 0..(3+x) (buffer + TERM data).
            TERM_L0: begin bytes_valid_o_d = sof_l4_active_q ? 8'b0000_1111 : 8'b0000_0000; in_frame_d = 1'b0; ipg_counter_d = 7; send_d = 1'b1; sof_l4_active_d = 1'b0; end
            TERM_L1: begin bytes_valid_o_d = sof_l4_active_q ? 8'b0001_1111 : 8'b0000_0010; in_frame_d = 1'b0; ipg_counter_d = 6; send_d = 1'b1; sof_l4_active_d = 1'b0; end
            TERM_L2: begin bytes_valid_o_d = sof_l4_active_q ? 8'b0011_1111 : 8'b0000_0110; in_frame_d = 1'b0; ipg_counter_d = 5; send_d = 1'b1; sof_l4_active_d = 1'b0; end
            TERM_L3: begin bytes_valid_o_d = sof_l4_active_q ? 8'b0111_1111 : 8'b0000_1110; in_frame_d = 1'b0; ipg_counter_d = 4; send_d = 1'b1; sof_l4_active_d = 1'b0; end
            TERM_L4: begin bytes_valid_o_d = sof_l4_active_q ? 8'b1111_1111 : 8'b0001_1110; in_frame_d = 1'b0; ipg_counter_d = 3; send_d = 1'b1; sof_l4_active_d = 1'b0; end
            // TERM_L5..L7 in SOF_L4 mode would need >8 trailing bytes split
            // across two emissions. Fall back to legacy SOF_L0 mask (the
            // QLogic-driven case we care about uses TERM_L4 for 64-byte
            // frames, so this is a documented gap; revisit if it shows up).
            TERM_L5: begin bytes_valid_o_d = 8'b0011_1110; in_frame_d = 1'b0; ipg_counter_d = 2; send_d = 1'b1; sof_l4_active_d = 1'b0; end  //b0111_1100   b0011_1110
            TERM_L6: begin bytes_valid_o_d = 8'b0111_1110; in_frame_d = 1'b0; ipg_counter_d = 1; send_d = 1'b1; sof_l4_active_d = 1'b0; end  //b0111_1110   b0111_1110
            TERM_L7: begin bytes_valid_o_d = 8'b1111_1110; in_frame_d = 1'b0; ipg_counter_d = 0; send_d = 1'b1; sof_l4_active_d = 1'b0; end

            // Ordered Set + Data Headers
            OS_D6:  bytes_valid_o_d = 8'b1110_1110;  //b0111_0111  b1110_1110
            OS_D5:  bytes_valid_o_d = 8'b1110_1110;  //b0111_0111  b1110_1110
            OS_D3T: bytes_valid_o_d = 8'b0000_1110;  //b0111_0000  b0000_1110
            OS_D3B: bytes_valid_o_d = 8'b1110_0000;  //b0000_0111  b1110_0000

            // anything else is invalid so needs to be dropped
            default: begin
                bytes_valid_o_d = 8'b0000_0000;
                in_frame_d      = 1'b0;
                drop_frame_o_d  = 1'b1;
                ipg_counter_d   = '0;
                drop_mode_d     = 1'b1;
                sof_l4_active_d = 1'b0;
            end
        endcase

    // Valid input, currently in frame and its a data header.
    //
    // SOF_L4 mode (sof_l4_active_q == 1):
    //   DATA1 (sof_l4_first_data_q): lanes 0-3 are preamble (drop), lanes 4-7
    //     are the first 4 MAC bytes — buffer them, emit nothing this cycle.
    //     This keeps the AXI tkeep clean (no non-contiguous mask).
    //   DATA2+: emit a re-packed 8-byte word combining the prior buffer (now
    //     at output lanes 0-3) with this block's incoming lanes 0-3 (now at
    //     output lanes 4-7). Buffer this block's lanes 4-7 for next cycle.
    //     out_data_o_d is muxed in the data-path always_comb above.
    //
    // SOF_L0 mode (legacy): pass through with full 0xFF mask.
    end else if (can_read && (header_bits_i == DATA_HDR) && in_frame_q) begin
        if (sof_l4_active_q) begin
            sof_l4_buf_d = input_data_i[63:32]; // capture upper 4 bytes (lanes 4-7)
            if (sof_l4_first_data_q) begin
                bytes_valid_o_d = 8'b0000_0000; // swallow DATA1, just buffer
            end else begin
                bytes_valid_o_d = 8'b1111_1111; // emit realigned 8 bytes
            end
        end else begin
            bytes_valid_o_d = 8'b1111_1111;
        end
        sof_l4_first_data_d = 1'b0;
    end

    out_valid_o_d = |bytes_valid_o_d;
end

// Clocked Outputs //

// ipg_counter_q
data_pipeline #(
    .DATA_W    (IPG_BIT_W),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (1),
    .RST_VAL   (0)
) data_pipeline_inst2 (
    .clk   (clk),
    .rst   (rst),
    .data_i(ipg_counter_d),
    .data_o(ipg_counter_q)
);

// ipg_check_en_d, ipg_check_en_q;
data_pipeline #(
    .DATA_W    (1),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (1),
    .RST_VAL   (0)
) data_pipeline_inst8 (
    .clk   (clk),
    .rst   (rst),
    .data_i(ipg_check_en_d),
    .data_o(ipg_check_en_q)
);

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
) data_pipeline_inst3 (
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
) data_pipeline_inst4 (
    .clk   (clk),
    .rst   (rst),
    .data_i(in_frame_d),
    .data_o(in_frame_q)
);

// sof_l4_first_data_d, sof_l4_first_data_q;
// One-shot flag set on SOF_L4 detection, cleared after the first DATA block
// emission (or on TERM/drop). Identifies the DATA1 block whose lanes 0-3 are
// trailing preamble bytes (to be dropped) and lanes 4-7 are the first 4 MAC
// bytes (to be buffered for the next emission).
data_pipeline #(
    .DATA_W    (1),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (1),
    .RST_VAL   (0)
) data_pipeline_inst10 (
    .clk   (clk),
    .rst   (rst),
    .data_i(sof_l4_first_data_d),
    .data_o(sof_l4_first_data_q)
);

// sof_l4_active_d/q: sticky flag, 1 throughout an SOF_L4 frame. Drives the
// byte-realignment data mux and the SOF_L4-aware TERM masks.
data_pipeline #(
    .DATA_W    (1),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (1),
    .RST_VAL   (0)
) data_pipeline_inst11 (
    .clk   (clk),
    .rst   (rst),
    .data_i(sof_l4_active_d),
    .data_o(sof_l4_active_q)
);

// sof_l4_buf_d/q: 4-byte buffer holding the upper half (lanes 4-7) of the
// most-recently-received DATA block in SOF_L4 mode. These bytes become
// lanes 0-3 of the next emission so AXI tkeep stays contiguous.
data_pipeline #(
    .DATA_W    (32),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (1),
    .RST_VAL   (0)
) data_pipeline_inst12 (
    .clk   (clk),
    .rst   (rst),
    .data_i(sof_l4_buf_d),
    .data_o(sof_l4_buf_q)
);

//out_valid_o_d
data_pipeline #(
    .DATA_W    (1),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (1),
    .RST_VAL   (0)
) data_pipeline_inst5 (
    .clk   (clk),
    .rst   (rst),
    .data_i(out_valid_o_d),
    .data_o(out_valid_o)
);

//out_data_o_d
data_pipeline #(
    .DATA_W    (DATA_OUT_W),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (1)
) data_pipeline_inst6 (
    .clk   (clk),
    .rst   (rst),
    .data_i(out_data_o_d),
    .data_o(out_data_o)
);

//bytes_valid_o_d
data_pipeline #(
    .DATA_W    (BYTES_OUT),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (1)
) data_pipeline_inst7 (
    .clk   (clk),
    .rst   (rst),
    .data_i(bytes_valid_o_d),
    .data_o(bytes_valid_o)
);

//send_o and send_d
data_pipeline #(
    .DATA_W    (1),
    .PIPE_DEPTH(PIPE_DEPTH),
    .RST_EN    (1)
) data_pipeline_inst9 (
    .clk   (clk),
    .rst   (rst),
    .data_i(send_d),
    .data_o(send_o)
);

endmodule