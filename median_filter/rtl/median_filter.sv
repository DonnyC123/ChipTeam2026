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

  localparam int X_COUNTER_W = $clog2(IMAGE_LEN);
  localparam int Y_COUNTER_W = $clog2(IMAGE_HEIGHT);
  localparam int SHIFT_REG_W = IMAGE_LEN + KERNEL_LEN - 1;

  filter_state_t                   state_d;
  filter_state_t                   state_q;

  logic          [X_COUNTER_W-1:0] x_counter_d;
  logic          [X_COUNTER_W-1:0] x_counter_q;

  logic          [Y_COUNTER_W-1:0] y_counter_d;
  logic          [Y_COUNTER_W-1:0] y_counter_q;

  pixel_t                          pixel_shift_reg_d[SHIFT_REG_W];
  pixel_t                          pixel_shift_reg_q[SHIFT_REG_W];
  pixel_t                          kernel           [ KERNEL_LEN] [KERNEL_LEN];

  pixel_t                          pixel_d;
  pixel_t                          pixel_q;

  logic                            x_inbounds;
  logic                            y_inbounds;
  logic                            kernel_valid;

  logic                            done_d;
  logic                            done_q;
  always_comb begin
    x_inbounds = x_counter_q != 0;
    y_inbounds = y_counter_q != 0;
  end

  always_comb begin
    pixel_shift_reg_d = pixel_shift_reg_q;

    if (pixel_valid_if_i.valid) begin
      pixel_shift_reg_d[0]               = pixel_valid_if_i.pixel;
      pixel_shift_reg_d[1:SHIFT_REG_W-1] = pixel_shift_reg_q[0:SHIFT_REG_W-2];
    end
  end

  always_comb begin
    kernel_valid = '0;
    done_d       = '0;
    x_counter_d  = x_counter_q;
    y_counter_d  = y_counter_q;
    state_d      = state_q;

    unique case (state_q)
      IDLE: begin
        x_counter_d = '0;
        y_counter_d = '0;

        if (start_i) begin
          state_d = PROCESS;
        end
      end

      PROCESS: begin
        if (pixel_valid_if_i.valid) begin
          x_counter_d  = x_counter_q + 1;
          kernel_valid = x_inbounds && y_inbounds;

          if (x_counter_q == IMAGE_LEN - 1) begin
            x_counter_d = '0;
            y_counter_d = y_counter_q + 1;

            if (y_counter_q == IMAGE_HEIGHT - 1) begin
              y_counter_d = '0;
              done_d      = 1'b1;
              state_d     = IDLE;
            end
          end
        end
      end
    endcase
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      state_q     <= IDLE;
      x_counter_q <= '0;
      y_counter_q <= '0;
    end else begin
      state_q           <= state_d;
      x_counter_q       <= x_counter_d;
      y_counter_q       <= y_counter_d;
      pixel_shift_reg_q <= pixel_shift_reg_d;
    end
  end

  always_comb begin
    kernel[0][0] = pixel_shift_reg_q[SHIFT_REG_W-1];
    kernel[0][1] = pixel_shift_reg_q[SHIFT_REG_W-2];
    kernel[1][0] = pixel_shift_reg_q[0];
    kernel[1][1] = pixel_valid_if_i.pixel;
  end

  median_kernel_calc median_kernel_calc_inst (
      .clk     (clk),
      .rst     (rst),
      .kernel_i(kernel),
      .pixel_o (pixel_d)
  );

  data_status_pipeline #(
      .DATA_W    ($bits(pixel_d)),
      .STATUS_W  (1),
      .PIPE_DEPTH(1)
  ) data_status_pipeline_inst (
      .clk     (clk),
      .rst     (rst),
      .data_i  ({>>{pixel_d}}),
      .status_i(kernel_valid),
      .data_o  ({>>{pixel_valid_if_o.pixel}}),
      .status_o(pixel_valid_if_o.valid)
  );

  localparam DONE_DELAY = 2;

  data_pipeline #(
      .DATA_W    (1),
      .PIPE_DEPTH(DONE_DELAY)
  ) done_pipeline_inst (
      .clk   (clk),
      .rst   (rst),
      .data_i(done_d),
      .data_o(done_q)
  );

  assign done_o = done_q;

endmodule
