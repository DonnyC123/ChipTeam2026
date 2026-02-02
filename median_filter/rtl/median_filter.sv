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

  typedef enum logic [1:0] {INIT, CALC, DONE} state_t;
  state_t  current_state, next_state;

  pixel_t buffer [IMAGE_LEN*(KERNEL_LEN-1)+KERNEL_LEN-1:0];
  pixel_t output_pixel;

  int pixel_count;

  always_ff @(posedge clk) begin
    if (rst) begin
        current_state <= INIT;
        buffer <= '{default: '0};
    end else begin
      current_state <= next_state;
      if(pixel_valid_if_i.valid)begin
        buffer[0] <= pixel_valid_if_i.pixel;
        for(int i = 1; i < IMAGE_LEN*(KERNEL_LEN-1)+KERNEL_LEN; i++)begin
          buffer[i] <= buffer[i-1];
        end
      end
      if (current_state == CALC) begin
        if (pixel_count >= (IMAGE_LEN * IMAGE_HEIGHT) - 1) begin
          pixel_count <= 0;
        end else begin
          pixel_count <= pixel_count + 1;
        end
      end
    end
  end
  
  always_comb begin
    next_state = current_state;
    output_pixel.red   = median_avg(buffer[0].red,   buffer[1].red,   buffer[IMAGE_LEN].red,   buffer[IMAGE_LEN+1].red);
    output_pixel.green = median_avg(buffer[0].green, buffer[1].green, buffer[IMAGE_LEN].green, buffer[IMAGE_LEN+1].green);
    output_pixel.blue  = median_avg(buffer[0].blue,  buffer[1].blue,  buffer[IMAGE_LEN].blue,  buffer[IMAGE_LEN+1].blue);    
    pixel_valid_if_o.valid = 1'b0;
    pixel_valid_if_o.pixel = '{default: '0};
    done_o = 1'b0;

    case(current_state)
      INIT: begin
        if (start_i) begin
          next_state = CALC;
        end else begin 
          next_state = INIT;
        end
      end

      CALC: begin
        pixel_valid_if_o.valid = pixel_valid_if_i.valid; 
        pixel_valid_if_o.pixel = output_pixel;
      end

      DONE: begin
        done_o = 1'b1;
        next_state = IDLE;     
      end
    endcase
  end

  function automatic logic [PIXEL_W-1:0] median_avg(input logic [PIXEL_W-1:0] a, b, c, d);
      logic [PIXEL_W-1:0] sorted[4];
      sorted = '{a, b, c, d};
      for (int i = 0; i < 4; i++) begin
        for (int j = i + 1; j < 4; j++) begin
          if (sorted[i] > sorted[j]) begin
            logic [PIXEL_W-1:0] temp;
            temp = sorted[i];
            sorted[i] = sorted[j];
            sorted[j] = temp;
          end
        end
      end
      return (sorted[1] + sorted[2]) / 2; 
    endfunction


endmodule
