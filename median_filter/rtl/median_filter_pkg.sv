package median_filter_pkg;

  localparam int KERNEL_LEN = 2;
  localparam int PIXEL_W    = 8;

  typedef struct packed{
    logic [PIXEL_W-1:0] red;
    logic [PIXEL_W-1:0] green;
    logic [PIXEL_W-1:0] blue;
  } pixel_t;

  // Add more to package down here

endpackage
