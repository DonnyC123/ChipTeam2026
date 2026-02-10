module median_filter #(
  parameter int IMAGE_LEN    = 1080,
  parameter int IMAGE_HEIGHT = 720,
  parameter bit DEBUG_PASSTHROUGH = 1'b0   //Debug flag to do passthrough without convolution
) (
  input  logic                 clk,
  input  logic                 rst,
  input  logic                 start_i,
         pixel_valid_if.slave  pixel_valid_if_i,
  output logic                 done_o,
         pixel_valid_if.master pixel_valid_if_o
);
  import median_filter_pkg::*;

  localparam int NUM_CHANNELS = 3;
  localparam int DATA_W       = PIXEL_W * NUM_CHANNELS;
  localparam int ADDR_W       = $clog2(IMAGE_LEN);
  localparam int ROW_W        = $clog2(IMAGE_HEIGHT);
  localparam int WINDOW_LEN   = KERNEL_LEN * KERNEL_LEN; 


  // BRAM signals
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


  // Stage S0 pipelined registers
  logic              started_q;
  logic [ADDR_W-1:0] curr_col_q, curr_col_d;
  logic [ROW_W-1:0]  curr_row_q, curr_row_d;

  logic              in_fire;
  logic [DATA_W-1:0] in_pixel_bus;

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

  // Check whether to process current pixel
  always_comb begin
    in_fire = started_q && pixel_valid_if_i.valid;
  end

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

  always_comb begin
    bram_rd_addr_i = curr_col_q;
    bram_wr_addr_i = curr_col_q;
    bram_wr_en_i   = in_fire;
    bram_wr_data_i = in_pixel_bus;
  end

  // S1 stage pipeline registers. Further pipeline because of BRAM latency
  logic              fire_s1_q;
  logic [DATA_W-1:0] pix_s1_q;
  logic [ADDR_W-1:0] col_s1_q;
  logic [ROW_W-1:0]  row_s1_q;


  logic [DATA_W-1:0] window_q   [0:WINDOW_LEN-1];
  logic [DATA_W-1:0] window_d   [0:WINDOW_LEN-1];

 
  always_comb begin
    for (int i = 0; i < WINDOW_LEN; i++) begin
      window_d[i] = window_q[i];
    end

    if (fire_s1_q) begin
      if (col_s1_q == 0) begin
        window_d[0] = '0;  
        window_d[2] = '0;  
      end else begin
        window_d[0] = window_q[1]; 
        window_d[2] = window_q[3]; 
      end

      window_d[1] = bram_rd_data_o;
      window_d[3] = pix_s1_q;
    end
  end


  function automatic logic [PIXEL_W-1:0] median4_chan(
    input logic [PIXEL_W-1:0] a,
    input logic [PIXEL_W-1:0] b,
    input logic [PIXEL_W-1:0] c,
    input logic [PIXEL_W-1:0] d
  );

    logic [PIXEL_W-1:0] low_1;
    logic [PIXEL_W-1:0] high_1;
    logic [PIXEL_W-1:0] low_2;
    logic [PIXEL_W-1:0] high_2;

    logic [PIXEL_W-1:0] lower_median;
    logic [PIXEL_W-1:0] upper_median;

    begin 
      if(a < b) begin
        low_1 = a;
        high_1 = b;
      end
      else begin 
        low_1 = b;
        high_1 = a;
      end

      if(c < d) begin
        low_2 = c;
        high_2 = d;
      end
      else begin 
        low_2 = d;
        high_2 = c;
      end
 
      lower_median = low_1 < low_2 ? low_2 : low_1;
      upper_median = high_1 < high_2 ? high_1 : high_2;

      
      median4_chan = (lower_median + upper_median + 1) >> 1;
    end
  endfunction


  function automatic logic [PIXEL_W-1:0] get_red  (input logic [DATA_W-1:0] px);
    return px[DATA_W-1 -: PIXEL_W];
  endfunction
  function automatic logic [PIXEL_W-1:0] get_green(input logic [DATA_W-1:0] px);
    return px[DATA_W-1-PIXEL_W -: PIXEL_W];
  endfunction
  function automatic logic [PIXEL_W-1:0] get_blue (input logic [DATA_W-1:0] px);
    return px[PIXEL_W-1:0];
  endfunction


  logic out_fire;
  always_comb begin
    out_fire = fire_s1_q && (row_s1_q > 0) && (col_s1_q > 0);
  end

  logic [PIXEL_W-1:0] red_out, green_out, blue_out;

  always_comb begin
    if (DEBUG_PASSTHROUGH) begin
      red_out   = get_red(window_d[3]);
      green_out = get_green(window_d[3]);
      blue_out  = get_blue(window_d[3]);
    end else begin
      red_out = median4_chan(
        get_red(window_d[0]),
        get_red(window_d[1]),
        get_red(window_d[2]),
        get_red(window_d[3])
      );
      green_out = median4_chan(
        get_green(window_d[0]),
        get_green(window_d[1]),
        get_green(window_d[2]),
        get_green(window_d[3])
      );
      blue_out = median4_chan(
        get_blue(window_d[0]),
        get_blue(window_d[1]),
        get_blue(window_d[2]),
        get_blue(window_d[3])
      );
    end
  end

  always_comb begin
    pixel_valid_if_o.valid       = 1'b0;
    pixel_valid_if_o.pixel.red   = '0;
    pixel_valid_if_o.pixel.green = '0;
    pixel_valid_if_o.pixel.blue  = '0;

    if (out_fire) begin
      pixel_valid_if_o.valid       = 1'b1;
      pixel_valid_if_o.pixel.red   = red_out;
      pixel_valid_if_o.pixel.green = green_out;
      pixel_valid_if_o.pixel.blue  = blue_out;
    end
  end

  logic done_pulse_d, done_pulse_q;
  always_comb begin
    done_pulse_d = out_fire
                && (row_s1_q == IMAGE_HEIGHT-1)
                && (col_s1_q == IMAGE_LEN-1);
    done_o = done_pulse_q;
  end


  always_ff @(posedge clk) begin
    if (rst) begin
      started_q    <= 1'b0;
      curr_col_q   <= '0;
      curr_row_q   <= '0;

      fire_s1_q    <= 1'b0;
      pix_s1_q     <= '0;
      col_s1_q     <= '0;
      row_s1_q     <= '0;

      done_pulse_q <= 1'b0;

      for (int i = 0; i < WINDOW_LEN; i++) begin
        window_q[i] <= '0;
      end
    end else begin
      if (start_i) begin
        started_q  <= 1'b1;
        curr_col_q <= '0;
        curr_row_q <= '0;

        fire_s1_q  <= 1'b0;

        for (int i = 0; i < WINDOW_LEN; i++) begin
          window_q[i] <= '0;
        end
      end else begin
        curr_col_q <= curr_col_d;
        curr_row_q <= curr_row_d;
        started_q  <= started_q;
      end

      fire_s1_q <= in_fire;
      if (in_fire) begin
        pix_s1_q <= in_pixel_bus;
        col_s1_q <= curr_col_q;
        row_s1_q <= curr_row_q;
      end

      if (fire_s1_q) begin
        for (int i = 0; i < WINDOW_LEN; i++) begin
          window_q[i] <= window_d[i];
        end
      end
      done_pulse_q <= done_pulse_d;
    end
  end

endmodule
