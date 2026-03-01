module alignment_finder #(
    parameter int DATA_WIDTH   = 66,
    parameter int GOOD_COUNT   = 32,
    parameter int BAD_COUNT    = 8,
    parameter int BITSLIP_WAIT = 3
) (
    input  logic                  clk,
    input  logic                  rst,
    input  logic                  data_valid_i,
    input  logic [DATA_WIDTH-1:0] data_i,

    output logic                  locked_o,
    output logic                  bitslip_o
);

  // WIDTHS for the good and bad counters and bitslip wait counter
  localparam int GOOD_W = (GOOD_COUNT <= 1) ? 1 : $clog2(GOOD_COUNT+1);
  localparam int BAD_W  = (BAD_COUNT  <= 1) ? 1 : $clog2(BAD_COUNT+1);
  localparam int BSW_W  = (BITSLIP_WAIT <= 0) ? 1 : $clog2(BITSLIP_WAIT+1);

  // FSM states
  typedef enum logic [1:0] {
    RESET        = 2'b00,
    SEARCH       = 2'b01,
    LOCKED       = 2'b10,
    BITSLIP_HOLD = 2'b11
  } state_t;

  state_t state, state_n;

  logic [GOOD_W-1:0]        good_count;
  logic [GOOD_W-1:0]        good_count_n;
  logic [BAD_W-1:0]         bad_count;
  logic [BAD_W-1:0]         bad_count_n;

  logic [BSW_W-1:0]         bsw_count;
  logic [BSW_W-1:0]         bsw_count_n;

  logic                     locked_n;
  logic                     bitslip_n;

  logic [1:0]               hdr;
  logic                     hdr_valid;

  //header validity check 
  assign hdr       = data_i[DATA_WIDTH-1 : DATA_WIDTH-2];    
  assign hdr_valid = (hdr == 2'b01) || (hdr == 2'b10);

  always_comb begin
    state_n      = state;
    good_count_n = good_count;
    bad_count_n  = bad_count;
    bsw_count_n    = bsw_count;

    locked_n     = locked_o;
    bitslip_n    = 1'b0;

    case (state)
      RESET: begin
        state_n      = SEARCH;
        locked_n     = 1'b0;
        good_count_n = '0;
        bad_count_n  = '0;
        bsw_count_n    = '0;
      end

      SEARCH: begin
        locked_n     = 1'b0;
        bad_count_n  = '0;

        if (data_valid_i) begin
          if (hdr_valid) begin
            if (good_count >= GOOD_COUNT-1) begin
              state_n      = LOCKED;
              locked_n     = 1'b1;
              good_count_n = '0;
            end else begin
              good_count_n = good_count + 1'b1;
            end
          end else begin
            bitslip_n    = 1'b1;
            good_count_n = '0;

            if (BITSLIP_WAIT > 0) begin
              state_n   = BITSLIP_HOLD;
              bsw_count_n = BITSLIP_WAIT[BSW_W-1:0];
            end
          end
        end
      end

      BITSLIP_HOLD: begin
        locked_n     = 1'b0;
        good_count_n = '0;
        bad_count_n  = '0;

        if (data_valid_i) begin
          if (bsw_count <= 1) begin
            state_n = SEARCH;
            bsw_count_n  = '0;
          end else begin
            bsw_count_n = bsw_count - 1'b1;
          end
        end
      end

      LOCKED: begin
        locked_n     = 1'b1;
        good_count_n = '0;

        if (data_valid_i) begin
          if (hdr_valid) begin
            bad_count_n = '0;
          end else begin
            if (bad_count >= BAD_COUNT-1) begin
              state_n     = SEARCH;
              locked_n    = 1'b0;
              bad_count_n = '0;
            end else begin
              bad_count_n = bad_count + 1'b1;
            end
          end
        end
      end

      default: begin
        state_n      = RESET;
        locked_n     = 1'b0;
        bitslip_n    = 1'b0;
        good_count_n = '0;
        bad_count_n  = '0;
        bsw_count_n    = '0;
      end
    endcase
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      state      <= RESET;
      locked_o   <= 1'b0;
      bitslip_o  <= 1'b0;
      good_count <= '0;
      bad_count  <= '0;
      bsw_count    <= '0;
    end else begin
      state      <= state_n;
      locked_o   <= locked_n;
      bitslip_o  <= bitslip_n;
      good_count <= good_count_n;
      bad_count  <= bad_count_n;
      bsw_count    <= bsw_count_n;
    end
  end

endmodule