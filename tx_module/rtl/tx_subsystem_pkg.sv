package tx_subsystem_pkg;
  import tx_fifo_pkg::*;

  localparam logic [DMA_VALID_W-1:0] DMA_KEEP_ALL = {DMA_VALID_W{1'b1}};

  function automatic logic keep_is_lsb_contiguous(input logic [DMA_VALID_W-1:0] keep);
    logic seen_zero;
    begin
      keep_is_lsb_contiguous = 1'b1;
      seen_zero = 1'b0;
      for (int i = 0; i < DMA_VALID_W; i++) begin
        if (!keep[i]) begin
          seen_zero = 1'b1;
        end else if (seen_zero) begin
          keep_is_lsb_contiguous = 1'b0;
        end
      end
    end
  endfunction
endpackage
