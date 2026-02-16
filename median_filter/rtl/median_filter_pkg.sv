package median_filter_pkg;

  localparam int KERNEL_LEN = 2;
  localparam int PIXEL_W    = 8;
  localparam int PIXEL_NUM  = KERNEL_LEN * KERNEL_LEN;

  typedef struct packed {
    logic [PIXEL_W-1:0] red;
    logic [PIXEL_W-1:0] green;
    logic [PIXEL_W-1:0] blue;
  } pixel_t;

  localparam int PIXEL_T_W = $bits(pixel_t);

  typedef enum logic [1:0] {
    IDLE,
    FILL_FIRST_ROW,
    PROCESSING,
    DONE
  } state_t;

endpackage
