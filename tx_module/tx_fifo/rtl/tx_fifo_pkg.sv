package tx_fifo_pkg;

  localparam int DMA_DATA_W   = 256;
  localparam int DMA_VALID_W  = 32;
  localparam int PCS_DATA_W   = 64;
  localparam int PCS_VALID_W  = 8;
  
  localparam int BEATS_PER_ENTRY = DMA_DATA_W / PCS_DATA_W;
  
  typedef struct packed {
    logic [DMA_DATA_W-1:0]  data;
    logic [DMA_VALID_W-1:0] valid;
    logic                   last;
  } fifo_entry_t;
  
  localparam int FIFO_ENTRY_W = $bits(fifo_entry_t);
  
endpackage
