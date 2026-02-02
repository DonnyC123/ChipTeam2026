module median_filter #(
  parameter int IMAGE_LEN    = 1080,
  parameter int IMAGE_HEIGHT = 720
) (
  input  logic                clk,
  input  logic                rst,
  input  logic                start_i,
         pixel_valid_if.slave  pixel_valid_if_i,
  output logic                done_o,
         pixel_valid_if.master pixel_valid_if_o
);
  import median_filter_pkg::*;

  localparam int NUM_CHANNELS = 3;
  localparam int DATA_W       = PIXEL_W * NUM_CHANNELS;
  localparam int ADDR_W       = $clog2(IMAGE_LEN);
  localparam int ROW_W        = $clog2(IMAGE_HEIGHT);
  localparam int WINDOW_LEN   = KERNEL_LEN * KERNEL_LEN;


  logic              bram_wr_en_i;
  logic [DATA_W-1:0] bram_wr_data_i;
  logic [ADDR_W-1:0] bram_wr_addr_i;
  logic [ADDR_W-1:0] bram_rd_addr_i;
  logic [DATA_W-1:0] bram_rd_data_o;

  bram #(
    .DATA_W (DATA_W),
    .ADDR_W (ADDR_W)
  ) bram_inst_prev (
    .clk       (clk),
    .wr_en_i   (bram_wr_en_i),
    .wr_data_i (bram_wr_data_i),
    .wr_addr_i (bram_wr_addr_i),
    .rd_addr_i (bram_rd_addr_i),
    .rd_data_o (bram_rd_data_o)
  );


  logic              started_d;
  logic              started_q;

  logic [ADDR_W-1:0] curr_col_d;
  logic [ADDR_W-1:0] curr_col_q;

  logic [ROW_W-1:0]  curr_row_d;
  logic [ROW_W-1:0]  curr_row_q;


  logic              in_fire;


  logic [DATA_W-1:0] in_pixel_bus;

  logic [DATA_W-1:0] pixel_pipe_d;
  logic [DATA_W-1:0] pixel_pipe_q;

  logic [ADDR_W-1:0] col_pipe_d;
  logic [ADDR_W-1:0] col_pipe_q;

  logic [ROW_W-1:0]  row_pipe_d;
  logic [ROW_W-1:0]  row_pipe_q;

  logic              fire_pipe_d;
  logic              fire_pipe_q;

  logic [DATA_W-1:0] window_d [0:WINDOW_LEN-1];
  logic [DATA_W-1:0] window_q [0:WINDOW_LEN-1];


  logic              out_fire;
  logic              last_out_fire;

  logic              done_pulse_d;
  logic              done_pulse_q;

  //Get pixel if valid
  always_comb begin
    in_pixel_bus = '0;
    if (pixel_valid_if_i.valid) begin
      in_pixel_bus = {
        pixel_valid_if_i.pixel.red,
        pixel_valid_if_i.pixel.green,
        pixel_valid_if_i.pixel.blue
      };
    end
  end


  always_comb begin
    started_d = started_q;
    if (start_i) begin
      started_d = 1'b1;
    end
  end

  //Check whether new pixel to process has come in
  always_comb begin
    in_fire = started_q && pixel_valid_if_i.valid;
  end


  //Handle row and column counter increment logic
  always_comb begin
    curr_col_d = curr_col_q;
    curr_row_d = curr_row_q;

    if (in_fire) begin
      if (curr_col_q == IMAGE_LEN-1) begin
        curr_col_d = '0;
        if (curr_row_q != IMAGE_HEIGHT-1) begin
          curr_row_d = curr_row_q + 1'b1;
        end
      end else begin
        curr_col_d = curr_col_q + 1'b1;
      end
    end
  end


  //Write current value in col to and read prev value in col from BRAM
  always_comb begin
    bram_rd_addr_i = curr_col_q;
    bram_wr_addr_i = curr_col_q;
    bram_wr_en_i   = in_fire;
    bram_wr_data_i = in_pixel_bus;
  end

  //Pipeline current pixel, row, and column values
  always_comb begin
    pixel_pipe_d = pixel_pipe_q;
    col_pipe_d   = col_pipe_q;
    row_pipe_d   = row_pipe_q;
    fire_pipe_d  = in_fire;

    if (in_fire) begin
      pixel_pipe_d = in_pixel_bus;
      col_pipe_d   = curr_col_q;
      row_pipe_d   = curr_row_q;
    end
  end


  always_comb begin
    for (int i = 0; i < WINDOW_LEN; i++) begin
      window_d[i] = window_q[i];
    end

    if (fire_pipe_q) begin
      if (col_pipe_q == 0) begin
        window_d[0] = '0;          
        window_d[2] = '0;          
      end else begin
        window_d[0] = window_q[1]; 
        window_d[2] = window_q[3]; 
      end

      window_d[1] = bram_rd_data_o; 
      window_d[3] = pixel_pipe_q;   
    end
  end

  
  logic [PIXEL_W-1:0] red_median;
  logic [PIXEL_W-1:0] green_median;
  logic [PIXEL_W-1:0] blue_median;

  int unsigned        max_red_i;
  int unsigned        min_red_i;
  logic [PIXEL_W-1:0] max_red_v;
  logic [PIXEL_W-1:0] min_red_v;

  //Get min and max channel indices

  //Red
  always_comb begin
    max_red_i = 0;
    min_red_i = 0;

    max_red_v = window_q[0][DATA_W-1 -: PIXEL_W];
    min_red_v = window_q[0][DATA_W-1 -: PIXEL_W];

    for (int i = 1; i < WINDOW_LEN; i++) begin
      logic [PIXEL_W-1:0] red_i;
      red_i = window_q[i][DATA_W-1 -: PIXEL_W];

      if (red_i > max_red_v) begin
        max_red_v = red_i;
        max_red_i = i;
      end

      if (red_i < min_red_v) begin
        min_red_v = red_i;
        min_red_i = i;
      end
    end
  end

  //Green  
  int unsigned        max_green_i;
  int unsigned        min_green_i;
  logic [PIXEL_W-1:0] max_green_v;
  logic [PIXEL_W-1:0] min_green_v;

  always_comb begin
    max_green_i = 0;
    min_green_i = 0;

    max_green_v = window_q[0][DATA_W-1-PIXEL_W -: PIXEL_W];
    min_green_v = window_q[0][DATA_W-1-PIXEL_W -: PIXEL_W];

    for (int i = 1; i < WINDOW_LEN; i++) begin
      logic [PIXEL_W-1:0] green_i;
      green_i = window_q[i][DATA_W-1-PIXEL_W -: PIXEL_W];

      if (green_i > max_green_v) begin
        max_green_v = green_i;
        max_green_i = i;
      end

      if (green_i < min_green_v) begin
        min_green_v = green_i;
        min_green_i = i;
      end
    end
  end

  //Blue
  int unsigned        max_blue_i;
  int unsigned        min_blue_i;
  logic [PIXEL_W-1:0] max_blue_v;
  logic [PIXEL_W-1:0] min_blue_v;

  always_comb begin
    max_blue_i = 0;
    min_blue_i = 0;

    max_blue_v = window_q[0][PIXEL_W-1:0];
    min_blue_v = window_q[0][PIXEL_W-1:0];

    for (int i = 1; i < WINDOW_LEN; i++) begin
      logic [PIXEL_W-1:0] blue_i;
      blue_i = window_q[i][PIXEL_W-1:0];

      if (blue_i > max_blue_v) begin
        max_blue_v = blue_i;
        max_blue_i = i;
      end

      if (blue_i < min_blue_v) begin
        min_blue_v = blue_i;
        min_blue_i = i;
      end
    end
  end

  //Get median channel values


  //Red
  always_comb begin
    logic [PIXEL_W:0] red_total;
    red_total = '0;

    for (int i = 0; i < WINDOW_LEN; i++) begin
      logic [PIXEL_W-1:0] red_i;
      red_i = window_q[i][DATA_W-1 -: PIXEL_W];

      if ((i != min_red_i) && (i != max_red_i)) begin
        red_total += red_i;
      end
    end

    red_median = (red_total + 1'b1) >> 1;
  end

  //Greem
  always_comb begin
    logic [PIXEL_W:0] green_total;
    green_total = '0;

    for (int i = 0; i < WINDOW_LEN; i++) begin
      logic [PIXEL_W-1:0] green_i;
      green_i = window_q[i][DATA_W-1-PIXEL_W -: PIXEL_W];

      if ((i != min_green_i) && (i != max_green_i)) begin
        green_total += green_i;
      end
    end

    green_median = (green_total + 1'b1) >> 1;
  end

  //Blue
  always_comb begin
    logic [PIXEL_W:0] blue_total;
    blue_total = '0;

    for (int i = 0; i < WINDOW_LEN; i++) begin
      logic [PIXEL_W-1:0] blue_i;
      blue_i = window_q[i][PIXEL_W-1:0];

      if ((i != min_blue_i) && (i != max_blue_i)) begin
        blue_total += blue_i;
      end
    end

    blue_median = (blue_total + 1'b1) >> 1;
  end


  always_comb begin
    out_fire = fire_pipe_q && (row_pipe_q > 0) && (col_pipe_q > 0);
  end

 
  always_comb begin
    pixel_valid_if_o.valid       = 1'b0;
    pixel_valid_if_o.pixel.red   = '0;
    pixel_valid_if_o.pixel.green = '0;
    pixel_valid_if_o.pixel.blue  = '0;

    if (out_fire) begin
      pixel_valid_if_o.valid       = 1'b1;
      pixel_valid_if_o.pixel.red   = red_median;
      pixel_valid_if_o.pixel.green = green_median;
      pixel_valid_if_o.pixel.blue  = blue_median;
    end
  end


  always_comb begin
    last_out_fire  = out_fire
                  && (row_pipe_q == IMAGE_HEIGHT-1)
                  && (col_pipe_q == IMAGE_LEN-1);

    done_pulse_d   = last_out_fire;
    done_o         = done_pulse_q;
  end

 
  always_ff @(posedge clk) begin
    if (rst) begin
      started_q     <= 1'b0;
      curr_col_q    <= '0;
      curr_row_q    <= '0;
      pixel_pipe_q  <= '0;
      col_pipe_q    <= '0;
      row_pipe_q    <= '0;
      fire_pipe_q   <= 1'b0;
      done_pulse_q  <= 1'b0;

      for (int i = 0; i < WINDOW_LEN; i++) begin
        window_q[i] <= '0;
      end
    end else begin
      started_q     <= started_d;
      curr_col_q    <= curr_col_d;
      curr_row_q    <= curr_row_d;
      pixel_pipe_q  <= pixel_pipe_d;
      col_pipe_q    <= col_pipe_d;
      row_pipe_q    <= row_pipe_d;
      fire_pipe_q   <= fire_pipe_d;
      done_pulse_q  <= done_pulse_d;

      for (int i = 0; i < WINDOW_LEN; i++) begin
        window_q[i] <= window_d[i];
      end
    end
  end

endmodule
