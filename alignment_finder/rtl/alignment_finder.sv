module alignment_finder #(
    parameter int DATA_WIDTH      = 66,  
    parameter int GOOD_COUNT      = 32, 
    parameter int BAD_COUNT       = 8   
) (
    input  logic                  clk,
    input  logic                  rst,        
    input  logic                  data_valid_i, 
    input  logic [DATA_WIDTH-1:0] data_i,

    output logic                  locked_o,   
    output logic                  bitslip_o    
);

  // good and bad widths for the counters
  localparam int GOOD_W = (GOOD_COUNT  <= 1) ? 1 : $clog2(GOOD_COUNT+1);
  localparam int BAD_W  = (BAD_COUNT <= 1) ? 1 : $clog2(BAD_COUNT+1);

  logic [GOOD_W-1:0] good_count;
  logic [BAD_W-1:0]  bad_count;

  // three states
  typedef enum logic [1:0] {
    RESET  = 2'b00,
    SEARCH = 2'b01,
    LOCKED = 2'b10
  } state_t;

  state_t state, state_n;

  // header
  logic [1:0] hdr;
  logic hdr_valid;

  // header comb logic
  assign hdr = data_i[65:64];
  assign hdr_valid = (hdr == 2'b01) || (hdr == 2'b10);

  // FSM comb logic (decides the next state)
  always_comb begin
    state_n   = state;
    bitslip_o = 1'b0;

    case (state)
      RESET: begin
        state_n = SEARCH;
      end

      SEARCH: begin
        if (data_valid_i) begin
          if (hdr_valid) begin
            if (good_count >= GOOD_COUNT-1)
              state_n = LOCKED;
          end else begin
            bitslip_o = 1'b1;     
            state_n   = SEARCH; 
          end
        end
      end

      LOCKED: begin
        if (data_valid_i) begin
          if (!hdr_valid && (bad_count >= BAD_COUNT-1))
            state_n = SEARCH;
        end
      end

      default: begin
        state_n = RESET;
      end
    endcase
  end

  // FSM sequential logic (state updates and counter updates)
  always_ff @(posedge clk) begin
    if (rst) begin
      state    <= RESET;
      locked_o <= 1'b0;
      good_count <= '0;
      bad_count  <= '0;
    end else begin
      state <= state_n;

      case (state)
        RESET: begin
          locked_o <= 1'b0;
          good_count <= '0;
          bad_count  <= '0;
        end

        SEARCH: begin
          locked_o <= 1'b0;

          if (data_valid_i) begin
            if (hdr_valid) begin
              if (good_count < GOOD_COUNT-1)
                good_count <= good_count + 1'b1;
              else
                good_count <= good_count;
            end else begin
              good_count <= '0;
            end
          end

          bad_count <= '0;

        end

        LOCKED: begin
          locked_o <= 1'b1;

          if (data_valid_i) begin
            if (hdr_valid) begin
              bad_count <= '0;
            end else begin
              if (bad_count < BAD_COUNT-1)
                bad_count <= bad_count + 1'b1;
              else
                bad_count <= bad_count;
            end
          end
          good_count <= '0;

          if (state_n == SEARCH) begin
            good_count <= '0;
            bad_count  <= '0;
            locked_o <= 1'b0;
          end
        end

        default: begin
          state    <= RESET;
          locked_o <= 1'b0;
          good_count <= '0;
          bad_count  <= '0;
        end
      endcase
    end
  end

endmodule