module median_filter_tb_top #(
  parameter int IMAGE_LEN    = 1080,
  parameter int IMAGE_HEIGHT = 720
)(
  input  logic clk,
  input  logic rst,

  input  logic start_i,

  // Flattened streaming input ports (match your Python seq item)
  input  logic        valid_i,
  input  logic [7:0]  red_i,
  input  logic [7:0]  green_i,
  input  logic [7:0]  blue_i,

  output logic done_o,

  // Flattened outputs too (for monitor)
  output logic        valid_o,
  output logic [7:0]  red_o,
  output logic [7:0]  green_o,
  output logic [7:0]  blue_o
);

  pixel_valid_if pixel_valid_if_i();
  pixel_valid_if pixel_valid_if_o();

  // Drive interface from flat inputs
  always_comb begin
    pixel_valid_if_i.valid       = valid_i;
    pixel_valid_if_i.pixel.red   = red_i;
    pixel_valid_if_i.pixel.green = green_i;
    pixel_valid_if_i.pixel.blue  = blue_i;
  end

  // Drive flat outputs from interface
  always_comb begin
    valid_o = pixel_valid_if_o.valid;
    red_o   = pixel_valid_if_o.pixel.red;
    green_o = pixel_valid_if_o.pixel.green;
    blue_o  = pixel_valid_if_o.pixel.blue;
  end

  median_filter #(
    .IMAGE_LEN(IMAGE_LEN),
    .IMAGE_HEIGHT(IMAGE_HEIGHT)
  ) dut (
    .clk(clk),
    .rst(rst),
    .start_i(start_i),
    .pixel_valid_if_i(pixel_valid_if_i),
    .done_o(done_o),
    .pixel_valid_if_o(pixel_valid_if_o)
  );

endmodule
