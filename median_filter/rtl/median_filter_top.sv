module median_filter_top #(
    parameter int IMAGE_LEN    = 1080,
    parameter int IMAGE_HEIGHT = 720
) (
    input  logic clk,
    input  logic rst,
    input  logic start_i,
    output logic done_o
);

  pixel_valid_if pixel_valid_if_i ();
  pixel_valid_if pixel_valid_if_o ();

  median_filter #(
      .IMAGE_LEN(IMAGE_LEN),
      .IMAGE_HEIGHT(IMAGE_HEIGHT)
  ) dut (
      .clk             (clk),
      .rst             (rst),
      .start_i         (start_i),
      .done_o          (done_o),
      .pixel_valid_if_i(pixel_valid_if_i),
      .pixel_valid_if_o(pixel_valid_if_o)
  );

endmodule

