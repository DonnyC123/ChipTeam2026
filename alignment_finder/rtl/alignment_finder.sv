module alignment_finder #(
    parameter int DATA_WIDTH   = 66,
    parameter int GOOD_COUNT   = 64,
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

  state_t state_q, state_d;

  logic [GOOD_W-1:0]        good_count_q;
  logic [GOOD_W-1:0]        good_count_d;
  logic [BAD_W-1:0]         bad_count_q;
  logic [BAD_W-1:0]         bad_count_d;

  logic [BSW_W-1:0]         bsw_count_q;
  logic [BSW_W-1:0]         bsw_count_d;

  logic                     locked_d;
  logic                     bitslip_d;

  logic [1:0]               hdr;
  logic                     hdr_valid;

  //header validity check 
  assign hdr       = data_i[1:0];
  assign hdr_valid = (hdr == 2'b01) || (hdr == 2'b10);

  always_comb begin
    state_d      = state_q;
    good_count_d = good_count_q;
    bad_count_d  = bad_count_q;
    bsw_count_d  = bsw_count_q;

    locked_d     = locked_o;
    bitslip_d    = 1'b0;

    case (state_q)
      RESET: begin
        state_d      = SEARCH;
        locked_d     = 1'b0;
        good_count_d = '0;
        bad_count_d  = '0;
        bsw_count_d  = '0;
      end

      SEARCH: begin
        locked_d     = 1'b0;
        bad_count_d  = '0;

        if (data_valid_i) begin
          if (hdr_valid) begin
            if (good_count_q == GOOD_COUNT-1) begin
              state_d      = LOCKED;
              locked_d     = 1'b1;
              good_count_d = '0;
            end else begin
              good_count_d = good_count_q + 1'b1;
            end
          end else begin
            bitslip_d    = 1'b1;
            good_count_d = '0;

            if (BITSLIP_WAIT > 0) begin
              state_d     = BITSLIP_HOLD;
              bsw_count_d = BITSLIP_WAIT;
            end
          end
        end
      end

      BITSLIP_HOLD: begin
        locked_d     = 1'b0;
        good_count_d = '0;
        bad_count_d  = '0;

        if (data_valid_i) begin
          if (bsw_count_q == 1) begin
            state_d = SEARCH;
            bsw_count_d = '0;
          end else begin
            bsw_count_d = bsw_count_q - 1;
          end
        end
      end

      LOCKED: begin
        locked_d     = 1'b1;
        good_count_d = '0;

        if (data_valid_i) begin
          if (hdr_valid) begin
            bad_count_d = '0;
          end else begin
            if (bad_count_q == BAD_COUNT-1) begin
              state_d     = SEARCH;
              locked_d    = 1'b0;
              bad_count_d = '0;
            end else begin
              bad_count_d = bad_count_q + 1;
            end
          end
        end
      end
    endcase
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      state_q      <= RESET;
      locked_o     <= 1'b0;
      bitslip_o    <= 1'b0;
      good_count_q <= '0;
      bad_count_q  <= '0;
      bsw_count_q  <= '0;
    end else begin
      state_q      <= state_d;
      locked_o     <= locked_d;
      bitslip_o    <= bitslip_d;
      good_count_q <= good_count_d;
      bad_count_q  <= bad_count_d;
      bsw_count_q  <= bsw_count_d;
    end
  end

endmodule