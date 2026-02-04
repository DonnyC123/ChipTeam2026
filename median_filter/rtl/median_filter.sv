module median_filter #(
    parameter int IMAGE_LEN    = 1080,
    parameter int IMAGE_HEIGHT = 720
) (
    input  logic            clk,
    input  logic            rst,
    input  logic            start_i,
    pixel_valid_if.slave    pixel_valid_if_i,
    output logic            done_o,
    pixel_valid_if.master   pixel_valid_if_o
);
  import median_filter_pkg::*;

  localparam int ADDR_W      = $clog2(IMAGE_LEN);
  localparam int ADDR_H      = $clog2(IMAGE_HEIGHT);
  localparam int PIXEL_W     = 24;

  logic                   bram_ena;
  logic                   bram_enb;

  logic [ADDR_W-1:0]      bram_addra;
  logic [ADDR_W-1:0]      bram_addrb;

  logic [PIXEL_W-1:0]     bram_data_d;
  logic [PIXEL_W-1:0]     bram_data_q;

  logic [PIXEL_W-1:0]     bram_data_pipe;

  bram #(
    .BRAM_ADDR_W (ADDR_W),
    .BRAM_DATA_W (PIXEL_W)
  ) line_buffer_bram (
    .clk                (clk),
    .addra              (bram_addra),
    .addrb              (bram_addrb),
    .ena                (bram_ena),
    .enb                (bram_enb),
    .bram_data_i        (bram_data_d),
    .bram_data_o        (bram_data_q)
  );

  logic [ADDR_W-1:0]    x_coord;
  logic [ADDR_H-1:0]    y_coord;
  logic [ADDR_W-1:0]    write_addr;
  logic [ADDR_W-1:0]    read_addr;
  logic                 read_active;

  logic [PIXEL_W-1:0]   d0, d1, d2, d3;

  // setting the x and y coordinate regs
  always_ff @(posedge clk) begin
    if(rst) begin
      x_coord     <= '0;
      y_coord     <= '0;
    end else begin
      if(pixel_valid_if_i.valid) begin
        if(x_coord == IMAGE_LEN - 1) begin
          x_coord <= '0;
          if(y_coord == IMAGE_HEIGHT - 1) begin
            y_coord <= '0;
          end else begin
            y_coord <= y_coord + 1;
          end
        end else begin
          x_coord <= x_coord + 1;
        end
      end
    end
  end

//incrementing write address
  always_ff @(posedge clk) begin
    if(rst) begin
      write_addr  <= 1'b0;
    end else
    if(pixel_valid_if_i.valid) begin
      write_addr  <= write_addr + 1;
    end
  end

//READING
  always_ff @(posedge clk) begin
    if(rst) begin
      read_active <= 1'b0;
      read_addr   <= '0;
    end else begin
      read_active <= (y_coord >= 1);

      if (read_active && pixel_valid_if_i.valid)
        read_addr <= write_addr - IMAGE_LEN;
    end
  end

  always_comb begin
    //READING COMB
    bram_enb      = read_active;
    bram_addrb    = read_addr;

    // WRITING COMB
    bram_addra    = write_addr;
    bram_data_d   = pixel_valid_if_i.pixel;
    bram_ena      = pixel_valid_if_i.valid;
  end

//d0 d1 .....
//d2 d3 .....

 always_ff @(posedge clk) begin
    if (rst)
      bram_data_pipe <= '0;
    else
      bram_data_pipe <= bram_data_q;
  end

// READING THE 4 PIXELS INTO D REGISTERS
  always_ff @(posedge clk) begin
    if(rst) begin
      d0          <= '0;
      d1          <= '0;
      d2          <= '0;
      d3          <= '0;
    end else 
    if(pixel_valid_if_i.valid) begin
      d3          <= pixel_valid_if_i.pixel;
      d2          <= d3;
      d1          <= bram_data_pipe;
      d0          <= d1;
    end
  end

  logic [10:0] red_total, green_total, blue_total;
  logic [7:0] max_red, min_red, max_green, min_green, max_blue, min_blue;
  max_module red_max (.a(d0.red), .b(d1.red), .c(d2.red), .d(d3.red), .out(max_red));
  max_module blue_max (.a(d0.blue), .b(d1.blue), .c(d2.blue), .d(d3.blue), .out(max_blue));
  max_module green_max (.a(d0.green), .b(d1.green), .c(d2.green), .d(d3.green), .out(max_green));

  min_module red_min (.a(d0.red), .b(d1.red), .c(d2.red), .d(d3.red), .out(min_red));
  min_module green_min (.a(d0.green), .b(d1.green), .c(d2.green), .d(d3.green), .out(min_green));
  min_module blue_min (.a(d0.blue), .b(d1.blue), .c(d2.blue), .d(d3.blue), .out(min_blue));

// Median filter logic
  always_comb begin
    red_total = d0.red+d1.red+d2.red+d3.red;
    green_total = d0.green+d1.green+d2.green+d3.green;
    blue_total = d0.blue+d1.blue+d2.blue+d3.blue;

    red_total = (red_total - max_red - min_red+1)/2;
    green_total = (green_total - max_green - min_green+1) >> 1;
    blue_total = (blue_total - max_blue - min_blue+1) >> 1;

    pixel_valid_if_o.pixel.red   = red_total[7:0];
    pixel_valid_if_o.pixel.green = green_total[7:0];
    pixel_valid_if_o.pixel.blue  = blue_total[7:0];
    
  end

  assign pixel_valid_if_o.valid = read_active && pixel_valid_if_i.valid && (x_coord >= 1);

endmodule

module max_module (input [7:0] a, input [7:0] b, input [7:0] c, input [7:0] d, output [7:0] out);
  logic [7:0] max1, max2;
  assign max1 = (a > b) ? a : b;
  assign max2 = (c > d) ? c : d;
  assign out = (max1 > max2) ? max1 : max2;
endmodule


module min_module (input [7:0] a, input [7:0] b, input [7:0] c, input [7:0] d, output [7:0] out);
  logic [7:0] min1, min2;
  assign min1 = (a < b) ? a : b;
  assign min2 = (c < d) ? c : d;
  assign out = (min1 < min2) ? min1 : min2;
endmodule