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
  import median_filter_pkg::*; // This gives us the pixel struct
  localparam int PIXELS_NEEDED = IMAGE_LEN + KERNEL_LEN;

  // Either wait for start, read pixels, or calculate output
  typedef enum logic [2:0] {IDLE, READ, CALCULATE} state_t;

  state_t state_q, state_d;
  pixel_t input_buffer_q [PIXELS_NEEDED- 1 : 0];
  pixel_t input_buffer_d [PIXELS_NEEDED- 1 : 0];
  logic [$clog2(PIXELS_NEEDED) - 1 : 0] pixel_ins_counter_q, pixel_ins_counter_d;
  logic [$clog2(IMAGE_LEN) - 1 : 0]     calculate_counter_q, calculate_counter_d;
  logic [$clog2(IMAGE_HEIGHT) - 1 : 0]  current_row_q, current_row_d;

  logic [2*PIXEL_W-1:0] middle_value_r;
  logic [2*PIXEL_W-1:0] middle_value_g;
  logic [2*PIXEL_W-1:0] middle_value_b;

  // Clocked process
  always_ff @(posedge clk) begin
    if(rst == 1'b1) begin
      state_q             <= IDLE;
      pixel_ins_counter_q <= '0;
      input_buffer_q      <= '0;
      calculate_counter_q <= '0;
      current_row_q <= '0;
    end else begin
      state_q             <= state_d;
      pixel_ins_counter_q <= pixel_ins_counter_d;
      input_buffer_q      <= input_buffer_d;
      calculate_counter_q <= calculate_counter_d;
      current_row_q <= current_row_d;
    end
  end

  // Combo block
  always_comb begin
    // set defaults (_d = combo, _q = ff)
    state_d                = state_q;
    pixel_ins_counter_d    = pixel_ins_counter_q;
    input_buffer_d         = input_buffer_q;
    calculate_counter_d    = calculate_counter_q;
    pixel_valid_if_o.valid = 1'b0;
    current_row_d          = current_row_q;
    done_o                 = 1'b0;

    case(state_q) 
      IDLE : begin
        if(start_i == 1'b1) begin
          pixel_ins_counter_d = '0;
          calculate_counter_d = '0;
          current_row_d       = '0;
          state_d             = READ;
        end else begin
          state_d = IDLE;
        end
      end

      READ : begin 
        if(pixel_valid_if_i.valid == 1'b1) begin

          for (int i = PIXELS_NEEDED-1; i > 0; i--) begin
            input_buffer_d[i] = input_buffer_q[i-1];
          end

          input_buffer_d[0]   = pixel_valid_if_i.pixel; // newest on the RHS
          pixel_ins_counter_d = pixel_ins_counter_q + 1;
          state_d             = READ; // so go to read

          if(pixel_ins_counter_d >= PIXELS_NEEDED) begin // if we have enough pixels 
            if(calculate_counter_q < IMAGE_LEN - 1) begin // and we can still calculate
              state_d = CALCULATE;  // then calculate
            end else begin  // if we need to get more pixels
              pixel_ins_counter_d = pixel_ins_counter_q - KERNEL_LEN; // we need to read kernel_len more pixels
            end
          end
        end
      end

      CALCULATE : begin  
        // can only run this image len-1 time before we need to wait kernal_length cycles
        // 2 x 2 = indexes: 0, 1, oldest, 2nd oldest
        middle_value_r = get_middle_values(input_buffer_q[input_buffer_q.high()].red,    
                                          input_buffer_q[input_buffer_q.high()-1].red,  
                                          input_buffer_q[input_buffer_q.low()].red,      
                                          input_buffer_q[input_buffer_q.low()+1].red);
        middle_value_g = get_middle_values(input_buffer_q[input_buffer_q.high()].green,    
                                  input_buffer_q[input_buffer_q.high()-1].green,  
                                  input_buffer_q[input_buffer_q.low()].green,      
                                  input_buffer_q[input_buffer_q.low()+1].green);
        middle_value_b = get_middle_values(input_buffer_q[input_buffer_q.high()].blue,    
                                  input_buffer_q[input_buffer_q.high()-1].blue,  
                                  input_buffer_q[input_buffer_q.low()].blue,      
                                  input_buffer_q[input_buffer_q.low()+1].blue);

        calculate_counter_d = calculate_counter_q + 1;
        state_d             = READ;

        if(calculate_counter_d == IMAGE_LEN - 2) begin 
          current_row_d       = current_row_q + 1;
          calculate_counter_d = '0;
          if(current_row_d == IMAGE_HEIGHT - 2) begin // exit condition
            state_d = IDLE; 
            done_o  = 1'b1;
          end 
        end
        

        // Outputs
        pixel_valid_if_o.pixel.red   = get_adverage(middle_value_r);
        pixel_valid_if_o.pixel.green = get_adverage(middle_value_g);
        pixel_valid_if_o.pixel.blue  = get_adverage(middle_value_b);
        pixel_valid_if_o.valid       = 1'b1;
      end

      default : begin
        // Defaults for glitches
        state_d             = IDLE;
        done_o              = 'x;
        pixel_ins_counter_d = 'x;
        input_buffer_d      = 'x;
        calculate_counter_d = 'x;
      end
    endcase
  end



endmodule
