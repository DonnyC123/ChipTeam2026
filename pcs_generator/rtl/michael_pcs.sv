module tx_pcs_generator #(
    parameter int DATA_W = 64,
    parameter int KEEP_W = DATA_W / 8,
    parameter int CONTROL_W = 2
) (
    input  logic                  clk,
    input  logic                  rst,
    
    input  logic [DATA_W-1:0]     in_data_i,
    input  logic [KEEP_W-1:0]     in_keep_i,
    input  logic                  in_last_i,
    input  logic                  in_valid_i,

    output logic                  in_ready_o,
    output logic [DATA_W-1:0]     out_data_o,
    output logic [CONTROL_W-1:0]  out_control_o,
    output logic                  out_valid_o,
    input  logic                  out_ready_i
);
  // TX 64b/66b PCS block generator (Clause 49/82 style, normal data path):
  // - out_control_o is the 2-bit sync header:
  //     2'b01 -> data block
  //     2'b10 -> control block
  // - out_data_o is the 64-bit 66b payload region.
  // - When no frame data is available, emit continuous Idle control blocks.
  // - Supports S0 start (0x78), D blocks, and T0..T7 terminate blocks.

  localparam logic [CONTROL_W-1:0] SYNC_DATA    = 2'b01;
  localparam logic [CONTROL_W-1:0] SYNC_CONTROL = 2'b10;

  localparam logic [7:0] BLOCK_IDLE      = 8'h1E;
  localparam logic [7:0] BLOCK_START_S0  = 8'h78;
  localparam logic [7:0] BLOCK_TERM_T0   = 8'h87;
  localparam logic [7:0] BLOCK_TERM_T1   = 8'h99;
  localparam logic [7:0] BLOCK_TERM_T2   = 8'hAA;
  localparam logic [7:0] BLOCK_TERM_T3   = 8'hB4;
  localparam logic [7:0] BLOCK_TERM_T4   = 8'hCC;
  localparam logic [7:0] BLOCK_TERM_T5   = 8'hD2;
  localparam logic [7:0] BLOCK_TERM_T6   = 8'hE1;
  localparam logic [7:0] BLOCK_TERM_T7   = 8'hFF;

  localparam logic [7:0] CTRL_IDLE_CODE  = 8'h00;
  localparam logic [KEEP_W-1:0] ALL_BYTES_VALID = {KEEP_W{1'b1}};
  localparam int SKID_DEPTH = 2;
  localparam int BYTE_BUF_BYTES = 64;
  localparam int BYTE_CNT_W = $clog2(BYTE_BUF_BYTES + 1);
  localparam int INGRESS_BYTE_W = 4;

  logic [DATA_W-1:0]      skid_data_q [0:SKID_DEPTH-1];
  logic [DATA_W-1:0]      skid_data_d [0:SKID_DEPTH-1];
  logic [KEEP_W-1:0]      skid_keep_q [0:SKID_DEPTH-1];
  logic [KEEP_W-1:0]      skid_keep_d [0:SKID_DEPTH-1];
  logic                   skid_last_q [0:SKID_DEPTH-1];
  logic                   skid_last_d [0:SKID_DEPTH-1];
  logic [1:0]             skid_count_q, skid_count_d;

  logic [7:0]             byte_data_q [0:BYTE_BUF_BYTES-1];
  logic [7:0]             byte_data_d [0:BYTE_BUF_BYTES-1];
  logic                   byte_eop_q [0:BYTE_BUF_BYTES-1];
  logic                   byte_eop_d [0:BYTE_BUF_BYTES-1];
  logic [BYTE_CNT_W-1:0]  byte_count_q, byte_count_d;

  logic                   in_frame_q, in_frame_d;
  logic                   need_t0_q, need_t0_d;
  logic                   short_frame_error_q, short_frame_error_d;
  logic                   ingress_in_pkt_q, ingress_in_pkt_d;
  logic [INGRESS_BYTE_W-1:0] ingress_pkt_bytes_q, ingress_pkt_bytes_d;

  logic [DATA_W-1:0]      out_data_q, out_data_d;
  logic [CONTROL_W-1:0]   out_control_q, out_control_d;
  logic                   out_valid_q, out_valid_d;

  logic                   can_move_from_skid_q;

  function automatic int unsigned keep_lsb_count(input logic [KEEP_W-1:0] keep);
    int unsigned count;
    begin
      count = 0;
      for (int i = 0; i < KEEP_W; i++) begin
        if (keep[i]) begin
          count++;
        end else begin
          break;
        end
      end
      return count;
    end
  endfunction

  function automatic logic keep_is_lsb_contiguous(input logic [KEEP_W-1:0] keep);
    logic seen_zero;
    begin
      keep_is_lsb_contiguous = 1'b1;
      seen_zero = 1'b0;
      for (int i = 0; i < KEEP_W; i++) begin
        if (!keep[i]) begin
          seen_zero = 1'b1;
        end else if (seen_zero) begin
          keep_is_lsb_contiguous = 1'b0;
        end
      end
    end
  endfunction

  function automatic logic [7:0] terminate_block_type(input int unsigned kbytes);
    begin
      case (kbytes)
        0: terminate_block_type = BLOCK_TERM_T0;
        1: terminate_block_type = BLOCK_TERM_T1;
        2: terminate_block_type = BLOCK_TERM_T2;
        3: terminate_block_type = BLOCK_TERM_T3;
        4: terminate_block_type = BLOCK_TERM_T4;
        5: terminate_block_type = BLOCK_TERM_T5;
        6: terminate_block_type = BLOCK_TERM_T6;
        7: terminate_block_type = BLOCK_TERM_T7;
        default: terminate_block_type = BLOCK_TERM_T0;
      endcase
    end
  endfunction

  function automatic logic [63:0] idle_block_payload();
    logic [63:0] payload;
    begin
      payload = '0;
      payload[7:0] = BLOCK_IDLE;
      for (int i = 1; i < 8; i++) begin
        payload[i*8 +: 8] = CTRL_IDLE_CODE;
      end
      return payload;
    end
  endfunction

  function automatic logic control_block_type_supported(input logic [7:0] block_type);
    begin
      case (block_type)
        BLOCK_IDLE,
        BLOCK_START_S0,
        BLOCK_TERM_T0,
        BLOCK_TERM_T1,
        BLOCK_TERM_T2,
        BLOCK_TERM_T3,
        BLOCK_TERM_T4,
        BLOCK_TERM_T5,
        BLOCK_TERM_T6,
        BLOCK_TERM_T7: control_block_type_supported = 1'b1;
        default: control_block_type_supported = 1'b0;
      endcase
    end
  endfunction

  assign can_move_from_skid_q = (skid_count_q != 0) && (byte_count_q <= (BYTE_BUF_BYTES - KEEP_W));
  assign in_ready_o = (skid_count_q < SKID_DEPTH) || ((skid_count_q == SKID_DEPTH) && can_move_from_skid_q);

  assign out_data_o    = out_data_q;
  assign out_control_o = out_control_q;
  assign out_valid_o   = out_valid_q;

  always_comb begin
    logic axis_accept;
    logic out_advance;
    logic [DATA_W-1:0] moved_data;
    logic [KEEP_W-1:0] moved_keep;
    logic moved_last;
    logic hold_accept;
    logic [DATA_W-1:0] hold_data;
    logic [KEEP_W-1:0] hold_keep;
    logic hold_last;
    logic [63:0] control_payload;
    int unsigned moved_bytes;
    int eop_pos;
    int short_eop_pos;
    int scan_limit;
    int unsigned kbytes;
    int unsigned accepted_bytes;
    int unsigned pkt_total_bytes;

    for (int i = 0; i < SKID_DEPTH; i++) begin
      skid_data_d[i] = skid_data_q[i];
      skid_keep_d[i] = skid_keep_q[i];
      skid_last_d[i] = skid_last_q[i];
    end
    for (int i = 0; i < BYTE_BUF_BYTES; i++) begin
      byte_data_d[i] = byte_data_q[i];
      byte_eop_d[i] = byte_eop_q[i];
    end

    skid_count_d = skid_count_q;
    byte_count_d = byte_count_q;
    in_frame_d = in_frame_q;
    need_t0_d = need_t0_q;
    short_frame_error_d = short_frame_error_q;
    ingress_in_pkt_d = ingress_in_pkt_q;
    ingress_pkt_bytes_d = ingress_pkt_bytes_q;

    out_data_d = out_data_q;
    out_control_d = out_control_q;
    out_valid_d = out_valid_q;
    hold_accept = 1'b0;
    hold_data = '0;
    hold_keep = '0;
    hold_last = 1'b0;

    axis_accept = in_valid_i && in_ready_o;
    out_advance = (!out_valid_q) || out_ready_i;

    if (axis_accept) begin
      accepted_bytes = in_last_i ? keep_lsb_count(in_keep_i) : KEEP_W;

      if (!ingress_in_pkt_q) begin
        pkt_total_bytes = accepted_bytes;
      end else begin
        pkt_total_bytes = ingress_pkt_bytes_q + accepted_bytes;
      end

      if (in_last_i) begin
        if (pkt_total_bytes < 7) begin
          short_frame_error_d = 1'b1;
        end
        ingress_in_pkt_d = 1'b0;
        ingress_pkt_bytes_d = '0;
      end else begin
        ingress_in_pkt_d = 1'b1;
        if (pkt_total_bytes >= 7) begin
          ingress_pkt_bytes_d = INGRESS_BYTE_W'(7);
        end else begin
          ingress_pkt_bytes_d = pkt_total_bytes[INGRESS_BYTE_W-1:0];
        end
      end

      if (skid_count_d == 0) begin
        skid_data_d[0] = in_data_i;
        skid_keep_d[0] = in_keep_i;
        skid_last_d[0] = in_last_i;
        skid_count_d = 1;
      end else if (skid_count_d == 1) begin
        skid_data_d[1] = in_data_i;
        skid_keep_d[1] = in_keep_i;
        skid_last_d[1] = in_last_i;
        skid_count_d = 2;
      end else begin
        hold_accept = 1'b1;
        hold_data = in_data_i;
        hold_keep = in_keep_i;
        hold_last = in_last_i;
      end
    end

    if ((skid_count_d != 0) && (byte_count_d <= (BYTE_BUF_BYTES - KEEP_W))) begin
      moved_data = skid_data_d[0];
      moved_keep = skid_keep_d[0];
      moved_last = skid_last_d[0];

      if (skid_count_d == 2) begin
        skid_data_d[0] = skid_data_d[1];
        skid_keep_d[0] = skid_keep_d[1];
        skid_last_d[0] = skid_last_d[1];
      end
      skid_data_d[1] = '0;
      skid_keep_d[1] = '0;
      skid_last_d[1] = 1'b0;
      skid_count_d = skid_count_d - 1'b1;

      moved_bytes = moved_last ? keep_lsb_count(moved_keep) : KEEP_W;
      for (int i = 0; i < KEEP_W; i++) begin
        if (i < moved_bytes) begin
          byte_data_d[byte_count_d + i] = moved_data[i*8 +: 8];
          byte_eop_d[byte_count_d + i] = moved_last && (i == (moved_bytes - 1));
        end
      end
      byte_count_d = byte_count_d + moved_bytes[BYTE_CNT_W-1:0];
    end

    if (hold_accept) begin
      if (skid_count_d == 0) begin
        skid_data_d[0] = hold_data;
        skid_keep_d[0] = hold_keep;
        skid_last_d[0] = hold_last;
        skid_count_d = 1;
      end else if (skid_count_d == 1) begin
        skid_data_d[1] = hold_data;
        skid_keep_d[1] = hold_keep;
        skid_last_d[1] = hold_last;
        skid_count_d = 2;
      end
    end

    if (out_advance) begin
      out_control_d = SYNC_CONTROL;
      out_data_d = idle_block_payload();
      out_valid_d = 1'b1;

      if (!in_frame_d) begin
        if (byte_count_d >= 7) begin
          short_eop_pos = -1;
          for (int i = 0; i < 7; i++) begin
            if ((short_eop_pos < 0) && byte_eop_d[i]) begin
              short_eop_pos = i;
            end
          end

          control_payload = '0;
          control_payload[7:0] = BLOCK_START_S0;
          for (int i = 0; i < 7; i++) begin
            control_payload[(i+1)*8 +: 8] = byte_data_d[i];
          end

          out_control_d = SYNC_CONTROL;
          out_data_d = control_payload;
          in_frame_d = 1'b1;
          need_t0_d = (short_eop_pos == 6);

          for (int i = 0; i < BYTE_BUF_BYTES; i++) begin
            if ((i + 7) < BYTE_BUF_BYTES) begin
              byte_data_d[i] = byte_data_d[i + 7];
              byte_eop_d[i] = byte_eop_d[i + 7];
            end else begin
              byte_data_d[i] = '0;
              byte_eop_d[i] = 1'b0;
            end
          end
          byte_count_d = byte_count_d - 7;
        end
      end else begin
        if (need_t0_d) begin
          control_payload = '0;
          control_payload[7:0] = BLOCK_TERM_T0;
          for (int i = 1; i < 8; i++) begin
            control_payload[i*8 +: 8] = CTRL_IDLE_CODE;
          end
          out_control_d = SYNC_CONTROL;
          out_data_d = control_payload;
          in_frame_d = 1'b0;
          need_t0_d = 1'b0;
        end else begin
          eop_pos = -1;
          scan_limit = (byte_count_d < 8) ? byte_count_d : 8;
          for (int i = 0; i < scan_limit; i++) begin
            if ((eop_pos < 0) && byte_eop_d[i]) begin
              eop_pos = i;
            end
          end

          if ((byte_count_d >= 8) && ((eop_pos < 0) || (eop_pos >= 7))) begin
            out_control_d = SYNC_DATA;
            out_data_d = '0;
            for (int i = 0; i < 8; i++) begin
              out_data_d[i*8 +: 8] = byte_data_d[i];
            end
            if (eop_pos == 7) begin
              need_t0_d = 1'b1;
            end

            for (int i = 0; i < BYTE_BUF_BYTES; i++) begin
              if ((i + 8) < BYTE_BUF_BYTES) begin
                byte_data_d[i] = byte_data_d[i + 8];
                byte_eop_d[i] = byte_eop_d[i + 8];
              end else begin
                byte_data_d[i] = '0;
                byte_eop_d[i] = 1'b0;
              end
            end
            byte_count_d = byte_count_d - 8;
          end else if ((eop_pos >= 0) && (eop_pos <= 6)) begin
            kbytes = eop_pos + 1;
            control_payload = '0;
            control_payload[7:0] = terminate_block_type(kbytes);
            for (int i = 0; i < 7; i++) begin
              if (i < kbytes) begin
                control_payload[(i+1)*8 +: 8] = byte_data_d[i];
              end else begin
                control_payload[(i+1)*8 +: 8] = CTRL_IDLE_CODE;
              end
            end
            out_control_d = SYNC_CONTROL;
            out_data_d = control_payload;

            for (int i = 0; i < BYTE_BUF_BYTES; i++) begin
              if ((i + kbytes) < BYTE_BUF_BYTES) begin
                byte_data_d[i] = byte_data_d[i + kbytes];
                byte_eop_d[i] = byte_eop_d[i + kbytes];
              end else begin
                byte_data_d[i] = '0;
                byte_eop_d[i] = 1'b0;
              end
            end
            byte_count_d = byte_count_d - kbytes[BYTE_CNT_W-1:0];
            in_frame_d = 1'b0;
            need_t0_d = 1'b0;
          end else begin
            // Wait for more bytes; do not report underflow or drop frame state.
            out_valid_d = 1'b0;
          end
        end
      end
    end
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      skid_count_q <= '0;
      byte_count_q <= '0;
      in_frame_q <= 1'b0;
      need_t0_q <= 1'b0;
      short_frame_error_q <= 1'b0;
      ingress_in_pkt_q <= 1'b0;
      ingress_pkt_bytes_q <= '0;
      out_data_q <= idle_block_payload();
      out_control_q <= SYNC_CONTROL;
      out_valid_q <= 1'b0;

      for (int i = 0; i < SKID_DEPTH; i++) begin
        skid_data_q[i] <= '0;
        skid_keep_q[i] <= '0;
        skid_last_q[i] <= 1'b0;
      end
      for (int i = 0; i < BYTE_BUF_BYTES; i++) begin
        byte_data_q[i] <= '0;
        byte_eop_q[i] <= 1'b0;
      end
    end else begin
      skid_count_q <= skid_count_d;
      byte_count_q <= byte_count_d;
      in_frame_q <= in_frame_d;
      need_t0_q <= need_t0_d;
      short_frame_error_q <= short_frame_error_d;
      ingress_in_pkt_q <= ingress_in_pkt_d;
      ingress_pkt_bytes_q <= ingress_pkt_bytes_d;
      out_data_q <= out_data_d;
      out_control_q <= out_control_d;
      out_valid_q <= out_valid_d;

      for (int i = 0; i < SKID_DEPTH; i++) begin
        skid_data_q[i] <= skid_data_d[i];
        skid_keep_q[i] <= skid_keep_d[i];
        skid_last_q[i] <= skid_last_d[i];
      end
      for (int i = 0; i < BYTE_BUF_BYTES; i++) begin
        byte_data_q[i] <= byte_data_d[i];
        byte_eop_q[i] <= byte_eop_d[i];
      end
    end
  end

`ifndef SYNTHESIS
  initial begin
    if (CONTROL_W < 2) begin
      $fatal(1, "tx_pcs_generator: CONTROL_W must be at least 2");
    end
    if (KEEP_W * 8 != DATA_W) begin
      $fatal(1, "tx_pcs_generator: KEEP_W must equal DATA_W/8");
    end
  end

  // AXIS assumptions/guards on accepted beats.
  property p_non_last_keep_full;
    @(posedge clk) disable iff (rst)
      (in_valid_i && !in_last_i && in_ready_o) |-> (in_keep_i == ALL_BYTES_VALID);
  endproperty
  a_non_last_keep_full: assert property (p_non_last_keep_full);

  property p_last_keep_nonzero;
    @(posedge clk) disable iff (rst)
      (in_valid_i && in_last_i && in_ready_o) |-> (in_keep_i != '0);
  endproperty
  a_last_keep_nonzero: assert property (p_last_keep_nonzero);

  property p_last_keep_contiguous;
    @(posedge clk) disable iff (rst)
      (in_valid_i && in_last_i && in_ready_o) |-> keep_is_lsb_contiguous(in_keep_i);
  endproperty
  a_last_keep_contiguous: assert property (p_last_keep_contiguous);

  // Upstream must hold payload stable while back-pressured.
  property p_axis_hold_while_wait;
    @(posedge clk) disable iff (rst)
      (in_valid_i && !in_ready_o && $past(in_valid_i && !in_ready_o))
      |-> ($stable(in_data_i) && $stable(in_keep_i) && $stable(in_last_i));
  endproperty
  a_axis_hold_while_wait: assert property (p_axis_hold_while_wait);

  // Outgoing payload must remain stable while stalled.
  property p_out_hold_while_wait;
    @(posedge clk) disable iff (rst)
      (out_valid_o && !out_ready_i) |=> (out_valid_o && $stable(out_data_o) && $stable(out_control_o));
  endproperty
  a_out_hold_while_wait: assert property (p_out_hold_while_wait);

  property p_sync_header_legal;
    @(posedge clk) disable iff (rst)
      out_valid_o |-> ((out_control_o == SYNC_DATA) || (out_control_o == SYNC_CONTROL));
  endproperty
  a_sync_header_legal: assert property (p_sync_header_legal);

  property p_control_block_type_legal;
    @(posedge clk) disable iff (rst)
      (out_valid_o && (out_control_o == SYNC_CONTROL))
      |-> control_block_type_supported(out_data_o[7:0]);
  endproperty
  a_control_block_type_legal: assert property (p_control_block_type_legal);

  property p_no_short_frame_error;
    @(posedge clk) disable iff (rst)
      !$rose(short_frame_error_q);
  endproperty
  a_no_short_frame_error: assert property (p_no_short_frame_error);

  c_idle_block_seen: cover property (
      @(posedge clk) out_valid_o && (out_control_o == SYNC_CONTROL) && (out_data_o[7:0] == BLOCK_IDLE)
  );
  c_start_block_seen: cover property (
      @(posedge clk) out_valid_o && (out_control_o == SYNC_CONTROL) && (out_data_o[7:0] == BLOCK_START_S0)
  );
  c_terminate_block_seen: cover property (
      @(posedge clk) out_valid_o && (out_control_o == SYNC_CONTROL) &&
      ((out_data_o[7:0] == BLOCK_TERM_T0) ||
       (out_data_o[7:0] == BLOCK_TERM_T1) ||
       (out_data_o[7:0] == BLOCK_TERM_T2) ||
       (out_data_o[7:0] == BLOCK_TERM_T3) ||
       (out_data_o[7:0] == BLOCK_TERM_T4) ||
       (out_data_o[7:0] == BLOCK_TERM_T5) ||
       (out_data_o[7:0] == BLOCK_TERM_T6) ||
       (out_data_o[7:0] == BLOCK_TERM_T7))
  );
`endif

endmodule