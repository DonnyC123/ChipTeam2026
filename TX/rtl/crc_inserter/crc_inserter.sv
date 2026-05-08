// CRC inserter — pipelined parallel CRC32.
//
// The per-cycle update crc_d = M · {data, crc_q} is linear over GF(2):
//   crc_d = M_data · data  ⊕  M_crc · crc_q
// The data half has no dependence on crc_q, so we precompute it in a
// stage-1 register. Stage 2 closes the feedback with just
//   (M_crc · crc_q) ⊕ data_contrib_s1_q
// — no path from data_i inside the recurrence, so the long net delay from
// tx_subsystem is no longer on the crc_q recurrence.
//
// Adds 1 cycle of latency. Backpressure is honored: stage 1 holds when
// stage 2 cannot consume (during S_TAIL), and stage 2 holds when downstream
// is not ready.
module crc_inserter #(
    parameter DATA_W = 64,
    parameter MASK_W = DATA_W / 8
) (
    input  logic              clk,
    input  logic              rst,

    input  logic [DATA_W-1:0] data_i,
    input  logic [MASK_W-1:0] mask_i,
    input  logic              valid_i,
    input  logic              last_i,
    input  logic              ready_i,

    output logic              ready_o,

    output logic [DATA_W-1:0] data_o,
    output logic [MASK_W-1:0] mask_o,
    output logic              valid_o,
    output logic              last_o
);

  localparam logic [31:0] CRC32_POLY = 32'h04C11DB7;
  localparam logic [31:0] CRC_INIT   = 32'hFFFFFFFF;
  localparam int unsigned IN_W       = 32 + DATA_W;

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

  // Elaboration-time symbolic CRC32 step for N bytes. Builds a 32 × IN_W
  // GF(2) matrix M such that crc_new = M · {data[N*8-1:0], crc_in}.
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

  // M · {data, crc_in} — full step.
  function automatic logic [31:0] mat_full(
      input logic [31:0][IN_W-1:0] M, input logic [DATA_W-1:0] data, input logic [31:0] crc_in);
    logic [31:0]     r;
    logic [IN_W-1:0] inp;
    inp = {data, crc_in};
    for (int i = 0; i < 32; i++) r[i] = ^(M[i] & inp);
    return r;
  endfunction

  // M · {data, 0} — data-only contribution. Stage-1 precompute.
  function automatic logic [31:0] mat_data(
      input logic [31:0][IN_W-1:0] M, input logic [DATA_W-1:0] data);
    logic [31:0]     r;
    logic [IN_W-1:0] inp;
    inp = {data, 32'b0};
    for (int i = 0; i < 32; i++) r[i] = ^(M[i] & inp);
    return r;
  endfunction

  // M · {0, crc_in} — crc-only feedback. Stage-2 short loop on crc_q.
  function automatic logic [31:0] mat_crc(
      input logic [31:0][IN_W-1:0] M, input logic [31:0] crc_in);
    logic [31:0]     r;
    logic [IN_W-1:0] inp;
    inp = {{DATA_W{1'b0}}, crc_in};
    for (int i = 0; i < 32; i++) r[i] = ^(M[i] & inp);
    return r;
  endfunction

  // -------------------------------------------------------------------------
  // Stage 1 combinational
  // -------------------------------------------------------------------------
  logic [3:0]  n_in;
  logic [31:0] data_contrib_d;
  logic [31:0] first_crc_d;     // first-beat full CRC: M · {data_i, CRC_INIT}

  always_comb begin
    n_in = '0;
    for (int i = 0; i < MASK_W; i++) n_in = n_in + {3'b0, mask_i[i]};

    data_contrib_d = '0;
    first_crc_d    = CRC_INIT;

    if (&mask_i) begin
      // Steady-state fast path — no popcount mux on this branch.
      data_contrib_d = mat_data(CRC_M8, data_i);
      first_crc_d    = mat_full(CRC_M8, data_i, CRC_INIT);
    end else begin
      unique case (n_in)
        4'd0: ;
        4'd1: begin data_contrib_d = mat_data(CRC_M1, data_i); first_crc_d = mat_full(CRC_M1, data_i, CRC_INIT); end
        4'd2: begin data_contrib_d = mat_data(CRC_M2, data_i); first_crc_d = mat_full(CRC_M2, data_i, CRC_INIT); end
        4'd3: begin data_contrib_d = mat_data(CRC_M3, data_i); first_crc_d = mat_full(CRC_M3, data_i, CRC_INIT); end
        4'd4: begin data_contrib_d = mat_data(CRC_M4, data_i); first_crc_d = mat_full(CRC_M4, data_i, CRC_INIT); end
        4'd5: begin data_contrib_d = mat_data(CRC_M5, data_i); first_crc_d = mat_full(CRC_M5, data_i, CRC_INIT); end
        4'd6: begin data_contrib_d = mat_data(CRC_M6, data_i); first_crc_d = mat_full(CRC_M6, data_i, CRC_INIT); end
        4'd7: begin data_contrib_d = mat_data(CRC_M7, data_i); first_crc_d = mat_full(CRC_M7, data_i, CRC_INIT); end
        4'd8: begin data_contrib_d = mat_data(CRC_M8, data_i); first_crc_d = mat_full(CRC_M8, data_i, CRC_INIT); end
        default: ;
      endcase
    end
  end

  // Stage 1 registers
  logic [DATA_W-1:0] data_s1_q;
  logic [MASK_W-1:0] mask_s1_q;
  logic              valid_s1_q;
  logic              last_s1_q;
  logic [31:0]       data_contrib_s1_q;
  logic [31:0]       first_crc_s1_q;
  logic [3:0]        n_s1_q;

  // -------------------------------------------------------------------------
  // Stage 2 — FSM operates on stage-1 registered signals.
  // -------------------------------------------------------------------------
  logic [      31:0] crc_q, crc_d;
  logic [       2:0] free_bytes_q, free_bytes_d;
  logic [DATA_W-1:0] data_d;
  logic [MASK_W-1:0] mask_d;
  logic              valid_d, last_d;

  // Short feedback half: M_crc_n · crc_q. Mid-frame n_s1_q == 8.
  logic [31:0] crc_feedback;
  always_comb begin
    unique case (n_s1_q)
      4'd0:    crc_feedback = crc_q;
      4'd1:    crc_feedback = mat_crc(CRC_M1, crc_q);
      4'd2:    crc_feedback = mat_crc(CRC_M2, crc_q);
      4'd3:    crc_feedback = mat_crc(CRC_M3, crc_q);
      4'd4:    crc_feedback = mat_crc(CRC_M4, crc_q);
      4'd5:    crc_feedback = mat_crc(CRC_M5, crc_q);
      4'd6:    crc_feedback = mat_crc(CRC_M6, crc_q);
      4'd7:    crc_feedback = mat_crc(CRC_M7, crc_q);
      4'd8:    crc_feedback = mat_crc(CRC_M8, crc_q);
      default: crc_feedback = crc_q;
    endcase
  end

  function automatic logic [2:0] free_slots(input logic [MASK_W-1:0] mask);
    logic [2:0] cnt;
    cnt = '0;
    for (int i = 0; i < MASK_W; i++) cnt += {2'b0, ~mask[i]};
    return cnt;
  endfunction

  logic [31:0] crc_final;
  logic        downstream_ready;
  logic        s1_advance;
  logic        s2_advance;

  assign crc_final        = ~reflect32(crc_q);
  assign downstream_ready = ready_i || !valid_o;

  // Stage 2 advances whenever the downstream output reg can accept.
  // Stage 1 also advances except in S_TAIL, where stage 2 is busy emitting
  // the tail and cannot consume the held stage-1 beat.
  assign s2_advance = downstream_ready;
  assign s1_advance = downstream_ready && (state_q != S_TAIL);
  assign ready_o    = s1_advance;

  always_comb begin
    state_d      = state_q;
    crc_d        = crc_q;
    free_bytes_d = free_bytes_q;

    data_d  = data_s1_q;
    mask_d  = mask_s1_q;
    valid_d = 1'b0;
    last_d  = 1'b0;

    unique case (state_q)

      S_IDLE: begin
        crc_d = CRC_INIT;
        if (valid_s1_q) begin
          crc_d        = first_crc_s1_q;
          free_bytes_d = free_slots(mask_s1_q);
          valid_d      = 1'b1;
          state_d      = S_STREAM;
        end
      end

      S_STREAM: begin
        if (valid_s1_q) begin
          crc_d        = crc_feedback ^ data_contrib_s1_q;
          free_bytes_d = free_slots(mask_s1_q);
          valid_d      = 1'b1;

          if (last_s1_q) begin
            logic [31:0] crc_out;
            crc_out = ~reflect32(crc_d);

            if (free_bytes_q >= 3'd4) begin
              logic [DATA_W-1:0] out_data;
              logic [MASK_W-1:0] out_mask;
              int                slot;
              out_data = data_s1_q;
              out_mask = mask_s1_q;
              slot     = 0;
              for (int b = 0; b < MASK_W; b++) begin
                if (!mask_s1_q[b] && slot < 4) begin
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
              out_data = data_s1_q;
              out_mask = mask_s1_q;
              slot     = 0;
              for (int b = 0; b < MASK_W; b++) begin
                if (!mask_s1_q[b]) begin
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
      state_q           <= S_IDLE;
      crc_q             <= CRC_INIT;
      free_bytes_q      <= '0;
      data_s1_q         <= '0;
      mask_s1_q         <= '0;
      valid_s1_q        <= 1'b0;
      last_s1_q         <= 1'b0;
      data_contrib_s1_q <= '0;
      first_crc_s1_q    <= CRC_INIT;
      n_s1_q            <= '0;
      data_o            <= '0;
      mask_o            <= '0;
      valid_o           <= 1'b0;
      last_o            <= 1'b0;
    end else begin
      if (s2_advance) begin
        data_o       <= data_d;
        mask_o       <= mask_d;
        valid_o      <= valid_d;
        last_o       <= last_d;
        state_q      <= state_d;
        crc_q        <= crc_d;
        free_bytes_q <= free_bytes_d;
      end
      if (s1_advance) begin
        data_s1_q         <= data_i;
        mask_s1_q         <= mask_i;
        valid_s1_q        <= valid_i;
        last_s1_q         <= last_i;
        data_contrib_s1_q <= data_contrib_d;
        first_crc_s1_q    <= first_crc_d;
        n_s1_q            <= n_in;
      end
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
