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

  function automatic logic [7:0] max4_u8(
      input logic [7:0] a,
      input logic [7:0] b,
      input logic [7:0] c,
      input logic [7:0] d
  );
      logic [7:0] m1, m2;
      begin
          m1 = (a > b) ? a : b;
          m2 = (c > d) ? c : d;
          max4_u8 = (m1 > m2) ? m1 : m2;
      end
  endfunction

  function automatic logic [7:0] min4_u8(
      input logic [7:0] a,
      input logic [7:0] b,
      input logic [7:0] c,
      input logic [7:0] d
  );
      logic [7:0] m1, m2;
      begin
          m1 = (a < b) ? a : b;
          m2 = (c < d) ? c : d;
          min4_u8 = (m1 < m2) ? m1 : m2;
      end
  endfunction

  function automatic pixel_t to_pixel_fn(input logic [23:0] a);
      pixel_t p;
      begin
          p.red   = a[23:16];
          p.green = a[15:8];
          p.blue  = a[7:0];
          return p;
      end
  endfunction

  function automatic logic [23:0] from_pixel_fn(input pixel_t a);
      begin
          from_pixel_fn = {a.red, a.green, a.blue};
      end
  endfunction

  logic                   bram_ena;
  logic                   bram_enb;

  logic [ADDR_W-1:0]      bram_addra;
  logic [ADDR_W-1:0]      bram_addrb;

  logic [PIXEL_W-1:0]     bram_data_d;
  logic [PIXEL_W-1:0]     bram_data_q;

  // stage 2 not really necessary
  pixel_t                 input_pipe1_d;
  pixel_t                 input_pipe1_q;
  pixel_t                 input_pipe2_d;
  pixel_t                 input_pipe2_q;
  logic                   input_pipe1_valid_d;
  logic                   input_pipe1_valid_q;
  logic                   input_pipe2_valid_d;
  logic                   input_pipe2_valid_q;
  logic                   input_pipe3_valid_d;
  logic                   input_pipe3_valid_q;

  logic                   output_pipe1_valid_d;
  logic                   output_pipe1_valid_q;
  logic                   output_pipe2_valid_d;
  logic                   output_pipe2_valid_q;
  logic                   output_pipe3_valid_d;
  logic                   output_pipe3_valid_q;

  logic                   done_valid_pipe1_d;
  logic                   done_valid_pipe1_q;
  logic                   done_valid_pipe2_d;
  logic                   done_valid_pipe2_q;
  logic                   done_valid_pipe3_d;
  logic                   done_valid_pipe3_q;

  logic [PIXEL_W-1:0]     bram_data_pipe;

  bram #(
    .BRAM_ADDR_WIDTH (ADDR_W),
    .BRAM_DATA_WIDTH (PIXEL_W)
  ) line_buffer_bram (
    .clk                  (clk),
    .addra                (bram_addra),
    .addrb                (bram_addrb),
    .ena                  (bram_ena),
    .enb                  (bram_enb),
    .bram_data_i          (bram_data_d),
    .bram_data_o          (bram_data_q)
  );

  logic [ADDR_W-1:0]      x_coord;
  logic [ADDR_H-1:0]      y_coord;
  logic [ADDR_W-1:0]      write_addr;
  logic [ADDR_W-1:0]      read_addr;
  logic                   read_active;

  pixel_t                 d0, d1, d2, d3;

  // setting the x and y coordinate regs (only valid for stage 0)
  always_ff @(posedge clk) begin
    if (rst) begin
      x_coord <= '0;
      y_coord <= '0;
    end else begin
      if (pixel_valid_if_i.valid) begin
        if (x_coord == IMAGE_LEN - 1) begin
          x_coord <= '0;
          if (y_coord == IMAGE_HEIGHT - 1)
            y_coord <= '0;
          else
            y_coord <= y_coord + 1;
        end else begin
          x_coord <= x_coord + 1;
        end
      end
    end
  end

  // incrementing write address
  always_ff @(posedge clk) begin
    if (rst)
      write_addr <= '0;
    else if (pixel_valid_if_i.valid)
      write_addr <= write_addr + 1;
  end

  // incrementing read address
  always_ff @(posedge clk) begin
    if (rst)
      read_addr <= '0;
    else if (read_active && pixel_valid_if_i.valid)
      read_addr <= read_addr + 1;
  end

  // comb for read_active
  assign read_active = (y_coord >= 1);

  // pack input pixel to BRAM data
  logic [23:0] bram_input;
  always_comb bram_input = from_pixel_fn(pixel_valid_if_i.pixel);

  always_comb begin
    // READING COMB
    bram_enb   = read_active && pixel_valid_if_i.valid;
    bram_addrb = read_addr;

    // WRITING COMB
    bram_ena   = pixel_valid_if_i.valid;
    bram_addra = write_addr;
    bram_data_d = bram_input;
  end

  // pipeline bram output
  always_ff @(posedge clk) begin
    if (rst)
      bram_data_pipe <= '0;
    else
      bram_data_pipe <= bram_data_q;
  end

  // pipelining the input data.
  always_ff @(posedge clk) begin
    if (rst) begin
      input_pipe1_valid_q <= 1'b0;
      input_pipe2_valid_q <= 1'b0;
      input_pipe3_valid_q <= 1'b0;

      output_pipe1_valid_q <= 1'b0;
      output_pipe2_valid_q <= 1'b0;
      output_pipe3_valid_q <= 1'b0;

      done_valid_pipe1_q <= 1'b0;
      done_valid_pipe2_q <= 1'b0;
      done_valid_pipe3_q <= 1'b0;
    end else begin
      input_pipe1_valid_q <= input_pipe1_valid_d;
      input_pipe2_valid_q <= input_pipe2_valid_d;
      input_pipe3_valid_q <= input_pipe3_valid_d;

      output_pipe1_valid_q <= output_pipe1_valid_d;
      output_pipe2_valid_q <= output_pipe2_valid_d;
      output_pipe3_valid_q <= output_pipe3_valid_d;

      done_valid_pipe1_q <= done_valid_pipe1_d;
      done_valid_pipe2_q <= done_valid_pipe2_d;
      done_valid_pipe3_q <= done_valid_pipe3_d;
    end

    input_pipe1_q <= input_pipe1_d;
    input_pipe2_q <= input_pipe2_d;
  end

  // pipeline stages signal logic
  always_comb begin
    input_pipe1_d       = pixel_valid_if_i.pixel;
    input_pipe1_valid_d = pixel_valid_if_i.valid && read_active;

    input_pipe2_d       = input_pipe1_q;
    input_pipe2_valid_d = input_pipe1_valid_q;

    input_pipe3_valid_d = input_pipe2_valid_q;

    output_pipe1_valid_d = pixel_valid_if_i.valid && (x_coord >= 1) && (y_coord >= 1);
    output_pipe2_valid_d = output_pipe1_valid_q;
    output_pipe3_valid_d = output_pipe2_valid_q;

    done_valid_pipe1_d = pixel_valid_if_i.valid && (x_coord == IMAGE_LEN-1) && (y_coord == IMAGE_HEIGHT-1);
    done_valid_pipe2_d = done_valid_pipe1_q;
    done_valid_pipe3_d = done_valid_pipe2_q;
  end

  // unpack BRAM data into pixel_t
  pixel_t bram_data_pipe_pixel;
  always_comb bram_data_pipe_pixel = to_pixel_fn(bram_data_pipe);

  // reading the 4 pixels into the d registers
  always_ff @(posedge clk) begin
    if (input_pipe2_valid_q) begin
      d3 <= input_pipe2_q;
      d2 <= d3;
      d1 <= bram_data_pipe_pixel;
      d0 <= d1;
    end
  end

  logic [10:0] red_total, green_total, blue_total;
  logic [7:0]  max_red, min_red, max_green, min_green, max_blue, min_blue;

  always_comb begin
    max_red   = max4_u8(d0.red,   d1.red,   d2.red,   d3.red);
    min_red   = min4_u8(d0.red,   d1.red,   d2.red,   d3.red);

    max_green = max4_u8(d0.green, d1.green, d2.green, d3.green);
    min_green = min4_u8(d0.green, d1.green, d2.green, d3.green);

    max_blue  = max4_u8(d0.blue,  d1.blue,  d2.blue,  d3.blue);
    min_blue  = min4_u8(d0.blue,  d1.blue,  d2.blue,  d3.blue);

    // Median filter logic
    red_total   = d0.red + d1.red + d2.red + d3.red;
    green_total = d0.green + d1.green + d2.green + d3.green;
    blue_total  = d0.blue + d1.blue + d2.blue + d3.blue;

    red_total   = (red_total   - max_red   - min_red   + 1) >> 1;
    green_total = (green_total - max_green - min_green + 1) >> 1;
    blue_total  = (blue_total  - max_blue  - min_blue  + 1) >> 1;

    pixel_valid_if_o.pixel.red   = red_total[7:0];
    pixel_valid_if_o.pixel.green = green_total[7:0];
    pixel_valid_if_o.pixel.blue  = blue_total[7:0];
  end

  assign pixel_valid_if_o.valid = output_pipe3_valid_q;
  assign done_o = input_pipe3_valid_q && done_valid_pipe3_q;

endmodule