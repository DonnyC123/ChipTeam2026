package rx_fifo_pkg;

  localparam BYTE_W = 8;

  let bin_to_gray(bin) = bin ^ (bin >> 1);
endpackage
