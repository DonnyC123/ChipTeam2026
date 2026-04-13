module median_kernel_calc
  import median_filter_pkg::*;
(
    input  logic   clk,
    input  logic   rst,
    input  pixel_t kernel_i[KERNEL_LEN][KERNEL_LEN],
    output pixel_t pixel_o
);

  logic [PIXEL_W-1:0] pixel_channel_median_red  [2];
  logic [PIXEL_W-1:0] pixel_channel_median_green[2];
  logic [PIXEL_W-1:0] pixel_channel_median_blue [2];

  always_comb begin
    find_median_channels(
        .pixel_channel(
        '{kernel_i[0][0].red, kernel_i[0][1].red, kernel_i[1][0].red, kernel_i[1][1].red}
        ),
        .pixel_channel_median(pixel_channel_median_red));

    pixel_o.red = average_pixel_channel(pixel_channel_median_red);

    find_median_channels(
        .pixel_channel(
        '{kernel_i[0][0].green, kernel_i[0][1].green, kernel_i[1][0].green, kernel_i[1][1].green}
        ),
        .pixel_channel_median(pixel_channel_median_green));

    pixel_o.green = average_pixel_channel(pixel_channel_median_green);

    find_median_channels(
        .pixel_channel(
        '{kernel_i[0][0].blue, kernel_i[0][1].blue, kernel_i[1][0].blue, kernel_i[1][1].blue}
        ),
        .pixel_channel_median(pixel_channel_median_blue));

    pixel_o.blue = average_pixel_channel(pixel_channel_median_blue);

  end

endmodule
