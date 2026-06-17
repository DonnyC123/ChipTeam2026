package median_filter_pkg;

  localparam int KERNEL_LEN = 2;
  localparam int PIXEL_W    = 8;

  typedef struct {
    logic [PIXEL_W-1:0] red;
    logic [PIXEL_W-1:0] green;
    logic [PIXEL_W-1:0] blue;
  } pixel_t;

  typedef enum int {
    IDLE,
    PROCESS
  } filter_state_t;

  function automatic logic [PIXEL_W-1:0] average_pixel_channel(
      logic [PIXEL_W-1:0] pixel_channel[2]);

    logic [PIXEL_W:0] sum;

    sum = pixel_channel[0] + pixel_channel[1];
    return (sum >> 1) + (sum[0]);
  endfunction

  function automatic void find_median_channels(input logic [PIXEL_W-1:0] pixel_channel[4],
                                               output logic [PIXEL_W-1:0] pixel_channel_median[2]);

    logic [PIXEL_W-1:0] pixel_channel_lower  [2];
    logic [PIXEL_W-1:0] pixel_channel_greater[2];


    pixel_channel_greater[0] = pixel_channel[0];
    pixel_channel_lower[0]   = pixel_channel[1];

    if (pixel_channel[0] < pixel_channel[1]) begin
      pixel_channel_greater[0] = pixel_channel[1];
      pixel_channel_lower[0]   = pixel_channel[0];
    end

    pixel_channel_greater[1] = pixel_channel[2];
    pixel_channel_lower[1]   = pixel_channel[3];

    if (pixel_channel[2] < pixel_channel[3]) begin
      pixel_channel_greater[1] = pixel_channel[3];
      pixel_channel_lower[1]   = pixel_channel[2];
    end

    pixel_channel_median[0] = pixel_channel_greater[0] < pixel_channel_greater[1]
                            ? pixel_channel_greater[0]
                            : pixel_channel_greater[1];

    pixel_channel_median[1] = pixel_channel_lower[0] < pixel_channel_lower[1]
                            ? pixel_channel_lower[1]
                            : pixel_channel_lower[0];

  endfunction

endpackage
