// Pad short frames up to MIN_FRAME_BYTES (default 60) by appending zero
// bytes before the FCS is computed. IEEE 802.3 requires the post-preamble
// MAC frame (DA + SA + LEN/TYPE + DATA) to be ≥ 60 bytes; when a host
// shorter than that is delivered (e.g. a 42-byte ARP without driver-side
// pad), this module zero-extends the last beat — and emits additional
// full-zero beats if needed — so `crc_inserter` sees a properly sized
// frame and `pcs_generator` can emit a clean TERM_L0 instead of a
// short-frame TERM_L<n> with leftover lanes.
//
// Assumes contiguous keep masks (mask_i ∈ {0x01, 0x03, ..., 0xFF}), the
// same convention `crc_inserter` enforces.
module pad_inserter #(
    parameter int DATA_W          = 64,
    parameter int MASK_W          = DATA_W / 8,
    parameter int MIN_FRAME_BYTES = 60
) (
    input  logic              clk,
    input  logic              rst,

    input  logic [DATA_W-1:0] data_i,
    input  logic [MASK_W-1:0] mask_i,
    input  logic              valid_i,
    input  logic              last_i,
    output logic              ready_o,

    input  logic              ready_i,
    output logic [DATA_W-1:0] data_o,
    output logic [MASK_W-1:0] mask_o,
    output logic              valid_o,
    output logic              last_o
);

  typedef enum logic { S_PASS, S_PAD } state_e;
  state_e state_q, state_d;

  // Bytes already emitted in the current frame (output side).
  logic [11:0] bytes_q, bytes_d;

  function automatic logic [3:0] popcount8(input logic [MASK_W-1:0] m);
    logic [3:0] s;
    s = '0;
    for (int i = 0; i < MASK_W; i++) s = s + {3'b0, m[i]};
    return s;
  endfunction

  // Build a contiguous mask of `n` bits set from bit 0 (n in 0..MASK_W).
  function automatic logic [MASK_W-1:0] mask_lsb(input logic [11:0] n);
    logic [MASK_W-1:0] m;
    m = '0;
    for (int i = 0; i < MASK_W; i++) if (i < int'(n)) m[i] = 1'b1;
    return m;
  endfunction

  // Zero-fill any bytes whose mask bit is 0 — keeps padding deterministic
  // even if upstream leaves stale data in unused lanes.
  logic [DATA_W-1:0] data_zero_filled;
  always_comb begin
    data_zero_filled = data_i;
    for (int b = 0; b < MASK_W; b++)
      if (!mask_i[b]) data_zero_filled[b*8+:8] = 8'h00;
  end

  always_comb begin
    state_d = state_q;
    bytes_d = bytes_q;

    valid_o = 1'b0;
    data_o  = '0;
    mask_o  = '0;
    last_o  = 1'b0;
    ready_o = 1'b0;

    unique case (state_q)
      S_PASS: begin
        // Default: pure pass-through.
        ready_o = ready_i;
        valid_o = valid_i;
        data_o  = data_i;
        mask_o  = mask_i;
        last_o  = last_i;

        if (valid_i && ready_i) begin
          logic [11:0] beat_bytes;
          logic [11:0] total_after;
          logic [11:0] needed;
          beat_bytes  = {8'b0, popcount8(mask_i)};
          total_after = bytes_q + beat_bytes;

          if (last_i) begin
            if (total_after >= MIN_FRAME_BYTES) begin
              // Frame is already large enough — emit unchanged.
              bytes_d = '0;
            end else begin
              // Need to add (MIN_FRAME_BYTES - bytes_q) bytes from this
              // beat onward.
              needed = MIN_FRAME_BYTES - bytes_q;
              data_o = data_zero_filled;

              if (needed <= MASK_W) begin
                // All remaining padding fits in the current beat.
                mask_o  = mask_lsb(needed);
                last_o  = 1'b1;
                bytes_d = '0;
              end else begin
                // Current beat goes out fully extended; remainder ships
                // from S_PAD on the following cycles.
                mask_o  = '1;
                last_o  = 1'b0;
                bytes_d = bytes_q + MASK_W;
                state_d = S_PAD;
              end
            end
          end else begin
            bytes_d = total_after;
          end
        end
      end

      S_PAD: begin
        logic [11:0] remaining;

        // Stall upstream while emitting pad beats.
        ready_o = 1'b0;
        valid_o = 1'b1;
        data_o  = '0;

        remaining = MIN_FRAME_BYTES - bytes_q;

        if (remaining > MASK_W) begin
          mask_o = '1;
          last_o = 1'b0;
        end else begin
          mask_o = mask_lsb(remaining);
          last_o = 1'b1;
        end

        if (ready_i) begin
          if (last_o) begin
            bytes_d = '0;
            state_d = S_PASS;
          end else begin
            bytes_d = bytes_q + MASK_W;
          end
        end
      end
    endcase
  end

  always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
      state_q <= S_PASS;
      bytes_q <= '0;
    end else begin
      state_q <= state_d;
      bytes_q <= bytes_d;
    end
  end

`ifndef SYNTHESIS
  // Catch non-contiguous masks early — same assumption crc_inserter enforces.
  always_ff @(posedge clk) begin
    if (!rst && valid_i && ready_o) begin
      automatic logic in_zero_run;
      in_zero_run = 1'b0;
      for (int b = 0; b < MASK_W; b++) begin
        if (!mask_i[b]) in_zero_run = 1'b1;
        else if (in_zero_run)
          $error("pad_inserter: non-contiguous mask_i=%b", mask_i);
      end
    end
  end

  // Every frame leaving this module must be ≥ MIN_FRAME_BYTES.
  int unsigned dbg_out_bytes_q;
  always_ff @(posedge clk or posedge rst) begin
    if (rst) dbg_out_bytes_q <= 0;
    else if (valid_o && ready_i) begin
      if (last_o) begin
        assert (dbg_out_bytes_q + popcount8(mask_o) >= MIN_FRAME_BYTES)
          else $error("pad_inserter: emitted frame of %0d bytes (< MIN=%0d)",
                      dbg_out_bytes_q + popcount8(mask_o), MIN_FRAME_BYTES);
        dbg_out_bytes_q <= 0;
      end else begin
        dbg_out_bytes_q <= dbg_out_bytes_q + popcount8(mask_o);
      end
    end
  end
`endif

endmodule
