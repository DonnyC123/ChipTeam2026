module median_filter #(
    parameter int IMAGE_LEN    = 1080,
    parameter int IMAGE_HEIGHT = 720
) (
    input  logic                 clk,
    input  logic                 rst,
    input  logic                 start_i,
           pixel_valid_if.slave  pixel_valid_if_i,
    output logic                 done_o,
           pixel_valid_if.master pixel_valid_if_o
);

import median_filter_pkg::*;

localparam int COL_CNT_W     = $clog2(IMAGE_LEN);
localparam int ROW_CNT_W     = $clog2(IMAGE_HEIGHT);
localparam int OUTPUT_LEN    = IMAGE_LEN - 1;
localparam int OUTPUT_HEIGHT = IMAGE_HEIGHT - 1;

state_t state_d, state_q;

logic [COL_CNT_W-1:0] col_cnt_d, col_cnt_q;
logic [ROW_CNT_W-1:0] row_cnt_d, row_cnt_q;

pixel_t line_buffer_d[IMAGE_LEN], line_buffer_q[IMAGE_LEN];
pixel_t prev_col_pixel_d, prev_col_pixel_q;
pixel_t window_pixels[4];

logic [PIXEL_W-1:0] red_values[4];
logic [PIXEL_W-1:0] green_values[4];
logic [PIXEL_W-1:0] blue_values[4];

logic [PIXEL_W-1:0] median_red;
logic [PIXEL_W-1:0] median_green;
logic [PIXEL_W-1:0] median_blue;

pixel_t output_pixel_d, output_pixel_q;
logic   output_valid_d, output_valid_q;
logic   done_d, done_q;

logic valid_input;
logic can_output;
logic is_last_pixel;
logic is_last_output;

always_comb begin
  window_pixels[0] = line_buffer_q[col_cnt_q-1];
  window_pixels[1] = line_buffer_q[col_cnt_q];
  window_pixels[2] = prev_col_pixel_q;
  window_pixels[3] = pixel_valid_if_i.pixel;
end

always_comb begin
  for (int i = 0; i < 4; i++) begin
    red_values[i]   = window_pixels[i].red;
    green_values[i] = window_pixels[i].green;
    blue_values[i]  = window_pixels[i].blue;
  end
end

median_of_4 #(
    .DATA_W(PIXEL_W)
) median_red_inst (
    .val_i   (red_values),
    .median_o(median_red)
);

median_of_4 #(
    .DATA_W(PIXEL_W)
) median_green_inst (
    .val_i   (green_values),
    .median_o(median_green)
);

median_of_4 #(
    .DATA_W(PIXEL_W)
) median_blue_inst (
    .val_i   (blue_values),
    .median_o(median_blue)
);

always_comb begin
  valid_input    = pixel_valid_if_i.valid &&
                    (state_q == FILL_FIRST_ROW || state_q == PROCESSING);
  can_output     = (state_q == PROCESSING) && (col_cnt_q > 0) && valid_input;
  is_last_pixel  = (col_cnt_q == IMAGE_LEN - 1) &&
                    (row_cnt_q == IMAGE_HEIGHT - 1);
  is_last_output = is_last_pixel && can_output;
end

always_comb begin
  state_d          = state_q;
  col_cnt_d        = col_cnt_q;
  row_cnt_d        = row_cnt_q;
  line_buffer_d    = line_buffer_q;
  prev_col_pixel_d = prev_col_pixel_q;
  output_pixel_d   = output_pixel_q;
  output_valid_d   = 1'b0;
  done_d           = 1'b0;

  case (state_q)

    IDLE: begin
      if (start_i) begin
        state_d   = FILL_FIRST_ROW;
        col_cnt_d = '0;
        row_cnt_d = '0;
      end
    end

    FILL_FIRST_ROW: begin
      if (valid_input) begin
        line_buffer_d[col_cnt_q] = pixel_valid_if_i.pixel;

        if (col_cnt_q == IMAGE_LEN - 1) begin
          col_cnt_d = '0;
          row_cnt_d = row_cnt_q + 1;
          state_d   = PROCESSING;
        end else begin
          col_cnt_d = col_cnt_q + 1;
        end
      end
    end

    PROCESSING: begin
      if (valid_input) begin
        line_buffer_d[col_cnt_q] = pixel_valid_if_i.pixel;
        prev_col_pixel_d         = pixel_valid_if_i.pixel;

        if (col_cnt_q > 0) begin
          output_valid_d       = 1'b1;
          output_pixel_d.red   = median_red;
          output_pixel_d.green = median_green;
          output_pixel_d.blue  = median_blue;
        end

        if (col_cnt_q == IMAGE_LEN - 1) begin
          col_cnt_d = '0;

          if (row_cnt_q == IMAGE_HEIGHT - 1) begin
            state_d = DONE;
          end else begin
            row_cnt_d = row_cnt_q + 1;
          end
        end else begin
          col_cnt_d = col_cnt_q + 1;
        end
      end
    end

    DONE: begin
      done_d  = 1'b1;
      state_d = IDLE;
    end

    default: begin
      state_d = IDLE;
    end

  endcase
end

always_ff @(posedge clk) begin
  if (rst) begin
    state_q          <= IDLE;
    col_cnt_q        <= '0;
    row_cnt_q        <= '0;
    prev_col_pixel_q <= '0;
    output_pixel_q   <= '0;
    output_valid_q   <= '0;
    done_q           <= '0;
  end else begin
    state_q          <= state_d;
    col_cnt_q        <= col_cnt_d;
    row_cnt_q        <= row_cnt_d;
    line_buffer_q    <= line_buffer_d;
    prev_col_pixel_q <= prev_col_pixel_d;
    output_pixel_q   <= output_pixel_d;
    output_valid_q   <= output_valid_d;
    done_q           <= done_d;
  end
end

assign pixel_valid_if_o.pixel = output_pixel_q;
assign pixel_valid_if_o.valid = output_valid_q;
assign done_o                 = done_q;

endmodule


module median_of_4 #(
  parameter int DATA_W = 8
) (
  input  logic [DATA_W-1:0] val_i[4],
  output logic [DATA_W-1:0] median_o
);

logic [DATA_W-1:0] stage1_lo_0, stage1_hi_0;
logic [DATA_W-1:0] stage1_lo_1, stage1_hi_1;
logic [DATA_W-1:0] stage2_lo,   stage2_hi;
logic [DATA_W-1:0] sorted[4];
logic [DATA_W:0]   sum;

always_comb begin
  if (val_i[0] > val_i[1]) begin
    stage1_lo_0 = val_i[1];
    stage1_hi_0 = val_i[0];
  end else begin
    stage1_lo_0 = val_i[0];
    stage1_hi_0 = val_i[1];
  end

  if (val_i[2] > val_i[3]) begin
    stage1_lo_1 = val_i[3];
    stage1_hi_1 = val_i[2];
  end else begin
    stage1_lo_1 = val_i[2];
    stage1_hi_1 = val_i[3];
  end

  if (stage1_lo_0 > stage1_lo_1) begin
    sorted[0] = stage1_lo_1;
    stage2_lo = stage1_lo_0;
  end else begin
    sorted[0] = stage1_lo_0;
    stage2_lo = stage1_lo_1;
  end

  if (stage1_hi_0 > stage1_hi_1) begin
    sorted[3] = stage1_hi_0;
    stage2_hi = stage1_hi_1;
  end else begin
    sorted[3] = stage1_hi_1;
    stage2_hi = stage1_hi_0;
  end

  if (stage2_lo > stage2_hi) begin
    sorted[1] = stage2_hi;
    sorted[2] = stage2_lo;
  end else begin
    sorted[1] = stage2_lo;
    sorted[2] = stage2_hi;
  end

  sum      = {1'b0, sorted[1]} + {1'b0, sorted[2]};
  median_o = sum[DATA_W:1] + {{(DATA_W - 1) {1'b0}}, sum[0]};
end

endmodule
