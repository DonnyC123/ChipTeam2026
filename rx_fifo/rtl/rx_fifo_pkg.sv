package rx_fifo_pkg;

  localparam BYTE_W = 8;

  let bin_to_gray(bin) = bin ^ (bin >> 1);

  function automatic logic [DATA_W-1:0] gray_to_bin
    #(DATA_W = 10) (input logic [DATA_W-1:0] gray);
   
    logic [DATA_W-1:0] bin = gray;
    
    for (int i = 1; i < DATA_W; i++) begin
      bin ^= gray >> i;
    end 

    return bin;
  endfunction
endpackage
