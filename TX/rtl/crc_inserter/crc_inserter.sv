module crc_inserter #(
    parameter DATA_W = 64,
    parameter MASK_W = DATA_W / 8
) (
    input logic clk,
    input logic rst,

    input logic [DATA_W-1:0] data_i,
    input logic [MASK_W-1:0] mask_i,
    input logic              valid_i,
    input logic              last_i,
    input logic              ready_i,

    output logic ready_o,

    output logic [DATA_W-1:0] data_o,
    output logic [MASK_W-1:0] mask_o,
    output logic              valid_o,
    output logic              last_o
);

  localparam logic [31:0] CRC32_POLY = 32'h04C11DB7;
  localparam logic [31:0] CRC_INIT   = 32'hFFFFFFFF;
  localparam int unsigned IN_W       = 32 + DATA_W;  // 96 for DATA_W=64

  typedef enum logic [1:0] {
    S_IDLE,
    S_STREAM,
    S_TAIL
  } state_e;

  state_e state_q, state_d;

  function automatic logic [31:0] reflect32(input logic [31:0] w);
    logic [31:0] r;
    for (int i = 0; i < 32; i++) r[i] = w[31 - i];
    return r;
  endfunction

  // Parallel CRC32 matrix generator — runs at elaboration time. Builds a
  // 32 × (32+N*8) GF(2) matrix M such that crc_new = M · {data[N*8-1:0], crc_in}
  // by symbolically running the bit-serial CRC32 update for N bytes starting
  // from the identity. Runtime cost collapses to a fixed XOR tree per output
  // bit (~5–6 LUT levels) instead of the original 64-deep serial chain.
  function automatic logic [31:0][IN_W-1:0] gen_crc32_matrix(input int unsigned n_bytes);
    logic [31:0][IN_W-1:0] state;
    logic [31:0][IN_W-1:0] next_state;
    logic [IN_W-1:0]       fb;

    for (int i = 0; i < 32; i++) begin
      state[i]    = '0;
      state[i][i] = 1'b1;
    end

    for (int j = 0; j < int'(n_bytes) * 8; j++) begin
      fb         = state[31];
      fb[32 + j] = fb[32 + j] ^ 1'b1;

      for (int k = 0; k < 32; k++) begin
        next_state[k] = (k == 0) ? '0 : state[k-1];
        if (CRC32_POLY[k]) next_state[k] = next_state[k] ^ fb;
      end
      state = next_state;
    end
    return state;
  endfunction

  localparam logic [31:0][IN_W-1:0] CRC_M1 = gen_crc32_matrix(1);
  localparam logic [31:0][IN_W-1:0] CRC_M2 = gen_crc32_matrix(2);
  localparam logic [31:0][IN_W-1:0] CRC_M3 = gen_crc32_matrix(3);
  localparam logic [31:0][IN_W-1:0] CRC_M4 = gen_crc32_matrix(4);
  localparam logic [31:0][IN_W-1:0] CRC_M5 = gen_crc32_matrix(5);
  localparam logic [31:0][IN_W-1:0] CRC_M6 = gen_crc32_matrix(6);
  localparam logic [31:0][IN_W-1:0] CRC_M7 = gen_crc32_matrix(7);
  localparam logic [31:0][IN_W-1:0] CRC_M8 = gen_crc32_matrix(8);

  // Full-word fast path: mid-frame beats always have mask = all-ones, so the
  // steady-state CRC update bypasses the popcount + 8-way matrix mux entirely
  // and uses just the M8 XOR tree. Saves ~3 LUT levels on the critical path.
  function automatic logic [31:0] crc32_full(
      input logic [31:0] crc_in, input logic [DATA_W-1:0] data);
    logic [IN_W-1:0] inp;
    logic [31:0]     r;
    inp = {data, crc_in};
    for (int i = 0; i < 32; i++) r[i] = ^(CRC_M8[i] & inp);
    return r;
  endfunction

  // Partial-word path: only used on the last beat when mask_i != all-ones.
  // ASSUMPTION: mask_i is contiguous from bit 0 (8'h01, 8'h03, ..., 8'hFF).
  function automatic logic [31:0] crc32_word(
      input logic [31:0] crc_in, input logic [DATA_W-1:0] data, input logic [MASK_W-1:0] mask);
    logic [IN_W-1:0] inp;
    logic [3:0]      n;
    logic [31:0]     r;

    inp = {data, crc_in};

    n = '0;
    for (int i = 0; i < MASK_W; i++) n = n + {3'b0, mask[i]};

    r = crc_in;
    unique case (n)
      4'd0:    r = crc_in;
      4'd1:    for (int i = 0; i < 32; i++) r[i] = ^(CRC_M1[i] & inp);
      4'd2:    for (int i = 0; i < 32; i++) r[i] = ^(CRC_M2[i] & inp);
      4'd3:    for (int i = 0; i < 32; i++) r[i] = ^(CRC_M3[i] & inp);
      4'd4:    for (int i = 0; i < 32; i++) r[i] = ^(CRC_M4[i] & inp);
      4'd5:    for (int i = 0; i < 32; i++) r[i] = ^(CRC_M5[i] & inp);
      4'd6:    for (int i = 0; i < 32; i++) r[i] = ^(CRC_M6[i] & inp);
      4'd7:    for (int i = 0; i < 32; i++) r[i] = ^(CRC_M7[i] & inp);
      4'd8:    for (int i = 0; i < 32; i++) r[i] = ^(CRC_M8[i] & inp);
      default: r = crc_in;
    endcase
    return r;
  endfunction

  // Pick full vs partial path. Mid-frame this is always the full path; only
  // the (rare) tail beat with non-full mask hits the popcount/mux.
  function automatic logic [31:0] crc32_step(
      input logic [31:0] crc_in, input logic [DATA_W-1:0] data, input logic [MASK_W-1:0] mask);
    if (&mask) return crc32_full(crc_in, data);
    else       return crc32_word(crc_in, data, mask);
  endfunction

  logic [      31:0] crc_q;
  logic [      31:0] crc_d;
  logic [DATA_W-1:0] held_data_q;
  logic [DATA_W-1:0] held_data_d;
  logic [MASK_W-1:0] held_mask_q;
  logic [MASK_W-1:0] held_mask_d;
  logic [       2:0] free_bytes_q;
  logic [       2:0] free_bytes_d;

  logic [DATA_W-1:0] data_d;
  logic [MASK_W-1:0] mask_d;
  logic              valid_d;
  logic              last_d;

  function automatic logic [2:0] free_slots(input logic [MASK_W-1:0] mask);
    logic [2:0] cnt;
    cnt = '0;
    for (int i = 0; i < MASK_W; i++) cnt += {2'b0, ~mask[i]};
    return cnt;
  endfunction

  logic [31:0] crc_final;
  logic [31:0] crc_next;
  logic        output_ready;

  assign crc_final    = ~reflect32(crc_q);
  assign output_ready = ready_i || !valid_o;

  always_comb begin
    state_d      = state_q;
    crc_d        = crc_q;
    held_data_d  = held_data_q;
    held_mask_d  = held_mask_q;
    free_bytes_d = free_bytes_q;

    ready_o      = 1'b0;
    data_d       = data_i;
    mask_d       = mask_i;
    valid_d      = 1'b0;
    last_d       = 1'b0;

    crc_next     = crc32_step(crc_q, data_i, mask_i);

    unique case (state_q)

      S_IDLE: begin
        ready_o = output_ready;
        crc_d   = CRC_INIT;

        if (valid_i && output_ready) begin
          crc_d        = crc32_step(CRC_INIT, data_i, mask_i);
          free_bytes_d = free_slots(mask_i);
          held_data_d  = data_i;
          held_mask_d  = mask_i;

          valid_d      = 1'b1;

          state_d      = S_STREAM;
        end
      end

      S_STREAM: begin
        ready_o = output_ready;

        if (valid_i && output_ready) begin
          crc_d        = crc_next;
          held_data_d  = data_i;
          held_mask_d  = mask_i;
          free_bytes_d = free_slots(mask_i);

          valid_d      = 1'b1;

          if (last_i) begin
            logic [31:0] crc_out;
            crc_out = ~reflect32(crc_d);

            if (free_bytes_q >= 3'd4) begin
              logic [DATA_W-1:0] out_data;
              logic [MASK_W-1:0] out_mask;
              int                slot;

              out_data = data_i;
              out_mask = mask_i;
              slot     = 0;

              for (int b = 0; b < MASK_W; b++) begin
                if (!mask_i[b] && slot < 4) begin
                  case (slot)
                    0: out_data[b*8+:8] = crc_out[7:0];
                    1: out_data[b*8+:8] = crc_out[15:8];
                    2: out_data[b*8+:8] = crc_out[23:16];
                    3: out_data[b*8+:8] = crc_out[31:24];
                  endcase
                  out_mask[b] = 1'b1;
                  slot++;
                end
              end

              data_d  = out_data;
              mask_d  = out_mask;
              last_d  = 1'b1;
              state_d = S_IDLE;
            end else begin
              logic [DATA_W-1:0] out_data;
              logic [MASK_W-1:0] out_mask;
              int                slot;

              out_data = data_i;
              out_mask = mask_i;
              slot     = 0;

              for (int b = 0; b < MASK_W; b++) begin
                if (!mask_i[b]) begin
                  case (slot)
                    0: out_data[b*8+:8] = crc_out[7:0];
                    1: out_data[b*8+:8] = crc_out[15:8];
                    2: out_data[b*8+:8] = crc_out[23:16];
                    3: out_data[b*8+:8] = crc_out[31:24];
                    default: ;
                  endcase
                  out_mask[b] = 1'b1;
                  slot++;
                end
              end

              data_d       = out_data;
              mask_d       = out_mask;
              last_d       = 1'b0;

              free_bytes_d = free_bytes_q;
              state_d      = S_TAIL;
            end
          end
        end
      end

      S_TAIL: begin
        logic [DATA_W-1:0] out_data;
        logic [MASK_W-1:0] out_mask;
        int                remaining;
        int                sent;

        ready_o   = 1'b0;
        valid_d   = 1'b1;
        last_d    = 1'b1;

        out_data  = '0;
        out_mask  = '0;
        sent      = int'(free_bytes_q);
        remaining = 4 - sent;

        for (int b = 0; b < MASK_W; b++) begin
          if (b < remaining) begin
            case (sent + b)
              0: out_data[b*8+:8] = crc_final[7:0];
              1: out_data[b*8+:8] = crc_final[15:8];
              2: out_data[b*8+:8] = crc_final[23:16];
              3: out_data[b*8+:8] = crc_final[31:24];
            endcase
            out_mask[b] = 1'b1;
          end
        end

        data_d  = out_data;
        mask_d  = out_mask;

        state_d = S_IDLE;
      end
    endcase
  end

  always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
      state_q      <= S_IDLE;
      crc_q        <= CRC_INIT;
      held_data_q  <= '0;
      held_mask_q  <= '0;
      free_bytes_q <= '0;
      data_o       <= '0;
      mask_o       <= '0;
      valid_o      <= 1'b0;
      last_o       <= 1'b0;
    end else if (output_ready) begin
      data_o       <= data_d;
      mask_o       <= mask_d;
      valid_o      <= valid_d;
      last_o       <= last_d;
      state_q      <= state_d;
      crc_q        <= crc_d;
      held_data_q  <= held_data_d;
      held_mask_q  <= held_mask_d;
      free_bytes_q <= free_bytes_d;
    end
  end

`ifndef SYNTHESIS
  always_ff @(posedge clk) begin
    if (!rst && valid_i && ready_o) begin
      automatic logic in_zero_run;
      in_zero_run = 1'b0;
      for (int b = 0; b < MASK_W; b++) begin
        if (!mask_i[b]) in_zero_run = 1'b1;
        else if (in_zero_run)
          $error("crc_inserter: non-contiguous mask_i=%b — parallel CRC matrix assumes mask is first-N-bytes-valid",
                 mask_i);
      end
    end
  end
`endif

endmodule
