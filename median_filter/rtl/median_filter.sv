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
  parameter int BUFFER_LEN = IMAGE_LEN*(KERNEL_LEN-1)+KERNEL_LEN;
  typedef enum logic [1:0] {INIT, CALC, DONE} state_t;
  state_t  state_q, state_c;

  pixel_t buffer_q [BUFFER_LEN-1:0];
  pixel_t buffer_c [BUFFER_LEN-1:0];
  pixel_t output_pixel_q, output_pixel_c;
  logic [$clog2(IMAGE_LEN)-1:0] x_counter_q, x_counter_c;
  logic [$clog2(IMAGE_HEIGHT)-1:0] y_counter_q, y_counter_c;


  int pixel_count;

  always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        current_state   <= INIT;
        buffer_q        <= 0;
        output_pixel_q  <= 0;
        x_counter_q     <= 0;
        y_counter_q     <= 0;
    end else begin
        state_q         <= state_c;
        output_pixel_q  <= output_pixel_c;
        x_counter_q     <= x_counter_c;
        y_counter_q     <= y_counter_c;
        buffer_q        <= buffer_c;
    end
  end
  
  always_comb begin
    state_c = state_q;
    pixel_valid_if_o.valid = 1'b0;
    pixel_valid_if_o.pixel = '{default: '0};
    done_o = 1'b0;
    x_counter_c = x_counter_q;
    y_counter_c = y_counter_q;
    buffer_c = buffer_q;

    case(state_c)
      INIT: begin
        if (start_i) begin
          state_c = CALC;
        end else begin 
          state_c = INIT;
        end
      end

      CALC: begin
        if(pixel_valid_if_i.valid || y_counter_q == IMAGE_HEIGHT - 1) begin
            if(x_counter_q == 0) begin
              buffer_c = {in_dout, buffer_q[BUFFER_LEN-1-: BUFFER_LEN-8]};
              x_counter_c = x_counter_q + 1;
              pixel_valid_if_o.valid = 1'b0;
              state_c = CALC;     
            end else if(x_counter_q == IMAGE_LEN - 1) begin
              buffer_c = {in_dout, buffer_q[BUFFER_LEN-1-: BUFFER_LEN-8]};
              x_counter_c = 0;
              pixel_valid_if_o.valid = 1'b0;
              y_counter_c = y_counter_q + 1;
              if (y_counter_q == IMAGE_HEIGHT - 1) begin
                  state_c = DONE;     
              end else begin 
                  state_c = CALC;     
              end
            end else begin
                output_pixel_c.red   = median_avg(buffer_q[0].red,   buffer_q[1].red,   buffer_q[IMAGE_LEN].red,   buffer_q[IMAGE_LEN+1].red);
                output_pixel_c.green = median_avg(buffer_q[0].green, buffer_q[1].green, buffer_q[IMAGE_LEN].green, buffer_q[IMAGE_LEN+1].green);
                output_pixel_c.blue  = median_avg(buffer_q[0].blue,  buffer_q[1].blue,  buffer_q[IMAGE_LEN].blue,  buffer_q[IMAGE_LEN+1].blue);    
                pixel_valid_if_o.valid = 1'b1;
                pixel_valid_if_o.pixel = output_pixel_c;
                state_c = CALC;     
            end
        end 
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
