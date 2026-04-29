package rx_fifo_pkg;

localparam int GRAY_BIN_W      = 16;
localparam int GRAY_COUNTER_W  = $clog2(GRAY_BIN_W);
localparam int FIFO_DATA_WIDTH = 64;


function automatic logic [FIFO_DATA_WIDTH-1:0] to01( input logic [FIFO_DATA_WIDTH-1:0] data );
    logic [FIFO_DATA_WIDTH-1:0] result;
    for ( int i=0; i < $bits(data); i++ ) begin
        case ( data[i] )  
            0: result[i]       = 1'b0;
            1: result[i]       = 1'b1;
            default: result[i] = 1'b0;
        endcase;
    end;
    return result;
endfunction

function automatic logic [GRAY_COUNTER_W-1:0] bin_to_gray(input logic [GRAY_COUNTER_W-1:0] count);
    return count ^ (count >> 1);
endfunction

function automatic logic [GRAY_BIN_W-1:0] gray_to_bin(input logic [GRAY_BIN_W-1:0] gray);
    logic [GRAY_BIN_W-1:0] bin;

    for (int i = 0; i < GRAY_BIN_W; i++) begin
        bin[i] = 1'b0;
        for (int j = i; j < GRAY_BIN_W; j++) begin
            bin[i] ^= gray[j];
        end
    end

    return bin;
endfunction

endpackage : rx_fifo_pkg