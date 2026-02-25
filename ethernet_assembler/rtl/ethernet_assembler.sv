// Ethernet 'Assembler' Planning:
// NOTE: The sequence item/transaction files dont exist yet.
// Inputs:
// - 66 bits of input_data_i (the MSB and MSB-1 are control signals, rest is data)
// - an bool in_valid_i signal which indicates if input_data_i is valid
// - a 'locked_i' bool signals which indicates that we are able to process our data
// Outputs:
// - A bool out_valid_o signal that indicates if any of the output bytes are valid
// - 64 bits called out_data_o (which is the input 66 minus the 2 control bits)
// - an array of 8 data_valid signals (bools) which indicate which bytes of out_data_o are valid
// Functionaility:
// - We need to parse the control bits (the MSB and MSB-1) from input_data_i
// - If those bits are equal to 10 this is a control payload, and we need to check the first byte of the data (bits 63:56) to decide what to do
//     - We reference the 64/66b chart to decide if this is a start/end/idle frame
//     - We set the data_valid array based on that
//     - We need a variale to track wether we are inside of a frame, that gets set/changed
// - else If those bits are == 01 this is a data frame, and if we are inside a frame, then we can set all of the data_valid signals to high
// 
// 0x2d block: four control characters followed by an ordered set
// 0x55 block: two ordered sets
// 0x4b block: ordered set followed by four control characters
// 0x66 block: ordered set followed by start and three data bytes.  (dont ignore this one)
// Basically the equivalent of 0x33, but with an ordered set before the start control character instead of four idles characters.


module ethernet_assembler #(
    parameter int DATA_IN_W   = 66,
    parameter int DATA_OUT_W  = 64
)(
    input logic                   clk,
    input logic                   rst,
    input logic                   in_valid_i,
    input logic                   locked_i,
    input logic  [DATA_IN_W-1:0]  input_data_i,
 
    output logic                  out_valid_o,
    output logic [DATA_OUT_W-1:0] out_data_o,
    output logic [BYTES_OUT-1:0]  bytes_valid_o
);

localparam logic [1:0] CTRL_HDR  = 2'b10;
localparam logic [1:0] DATA_HDR  = 2'b01;
localparam int         BYTES_OUT = DATA_OUT_W / 8;

logic [1:0]            header_bits;
logic [BYTES_OUT-1:0]  bytes_valid_o_d;
logic [DATA_OUT_W-1:0] out_data_o_d;
logic [7:0]            control_byte;
logic                  out_valid_o_d;
logic                  can_read;
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

assign out_data_o_d = bit_reverse(input_data_i[DATA_OUT_W-1:0]);
assign can_read     = in_valid_i && locked_i;
// TODO: I dont actually know if the sync/control bits is in network orders
assign header_bits  = {input_data_i[DATA_IN_W-2], input_data_i[DATA_IN_W-1]}; // Filp sync/control bits from network -> regular order
assign control_byte = out_data_o_d[DATA_OUT_W-1 -: 8];

always_comb begin
    // defaults
    out_valid_o_d   = 1'b0;
    bytes_valid_o_d = '0;
    in_frame_d      = in_frame_q;

    if (can_read && !in_frame_q && (header_bits == CTRL_HDR)) begin
        unique case (control_byte)
            // Start Frame Headers
            8'h78: begin bytes_valid_o_d = 8'b0111_1111; in_frame_d = 1'b1; end
            8'h33: begin bytes_valid_o_d = 8'b0000_0111; in_frame_d = 1'b1; end

            default: begin bytes_valid_o_d = 8'b0000_0000; in_frame_d = 1'b0; end
        endcase

    // Valid input, currently in-frame, and control header.
    end else if (can_read && in_frame_q && (header_bits == CTRL_HDR)) begin
        unique case (control_byte)
            // End Frame Headers
            8'h87: begin bytes_valid_o_d = 8'b0000_0000; in_frame_d = 1'b0; end
            8'h99: begin bytes_valid_o_d = 8'b0100_0000; in_frame_d = 1'b0; end
            8'hAA: begin bytes_valid_o_d = 8'b0110_0000; in_frame_d = 1'b0; end
            8'hB4: begin bytes_valid_o_d = 8'b0111_0000; in_frame_d = 1'b0; end
            8'hCC: begin bytes_valid_o_d = 8'b0111_1000; in_frame_d = 1'b0; end
            8'hD2: begin bytes_valid_o_d = 8'b0111_1100; in_frame_d = 1'b0; end
            8'hE1: begin bytes_valid_o_d = 8'b0111_1110; in_frame_d = 1'b0; end
            8'hFF: begin bytes_valid_o_d = 8'b0111_1111; in_frame_d = 1'b0; end

            // Ordered Set + Data Headers
            8'h66: bytes_valid_o_d = 8'b0111_0111;
            8'h55: bytes_valid_o_d = 8'b0111_0111;
            8'h4B: bytes_valid_o_d = 8'b0111_0000;
            8'h2D: bytes_valid_o_d = 8'b0000_0111;

            default: bytes_valid_o_d = 8'b0000_0000;
        endcase

    // Valid input, currently in-frame, and data header.
    end else if (can_read && (header_bits == DATA_HDR) && in_frame_q) begin
        bytes_valid_o_d = 8'b1111_1111;
    end

    out_valid_o_d = |bytes_valid_o_d;
end

// Clocked_i Outputs
always_ff @(posedge clk) begin
    if (rst) begin
        in_frame_q    <= 1'b0;
        bytes_valid_o <= 8'h00;
        out_valid_o   <= 1'b0; 
    end else begin
        in_frame_q    <= in_frame_d;
        bytes_valid_o <= bytes_valid_o_d;
        out_data_o    <= out_data_o_d;
        out_valid_o   <= out_valid_o_d;
    end
end

endmodule
