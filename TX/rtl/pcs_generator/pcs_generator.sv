// IEEE 802.3 Cl. 49 PCS framer.
//
// Block layout (lane 0 = first byte on the wire):
//   IDLE  : { 7×0x00, IDLE_BLK=0x1E }
//   SOF_L0: { 0xd5, 6×0x55, SOF_L0=0x78 }   ← lanes 1-7 are the trailing 7
//                                             bytes of preamble+SFD; the MAC
//                                             frame starts at lane 0 of the
//                                             NEXT block, so SOF consumes
//                                             zero AXI bytes.
//   DATA  : full 8 bytes from the AXI beat
//   TERM_n: n data bytes in lanes 0..n-1, T-byte in lane n, idle in n+1..7
//
// We always emit SOF_L0 (never SOF_L4) — the IPG bookkeeping in the receiver
// allows it and dropping SOF_L4 removes a pile of held-byte / leftover-byte
// state that used to track AXI-byte phase.

import pcs_pkg::*;

module pcs_generator #() (
    input  logic                 clk,
    input  logic                 rst,
    input  logic                 out_ready_i,
    output logic [DATA_W-1:0]    out_data_o,
    output logic [CONTROL_W-1:0] out_control_o,
    output logic                 out_valid_o,

    tx_axis_if.slave             axis_slave_if
);

  skid_entry_t skid_value_q, skid_value_d;

  typedef enum logic [1:0] { WAIT_START, DATA, EOF, IDLE_OUT } state_t;
  state_t current_state, next_state;

  logic       can_read;
  logic       get_axi;
  logic       next_is_last;
  logic       consume_skid;
  logic [3:0] num_incoming_d, num_incoming_q;

  logic [CONTROL_W-1:0] out_control_d;
  logic [DATA_W-1:0]    out_data_d;
  logic                 out_valid_d;
  logic                 tready_d;

  assign get_axi      = axis_slave_if.tvalid && axis_slave_if.tready;
  assign next_is_last = get_axi && axis_slave_if.tlast;
  assign can_read     = skid_value_q.valid_data_i && out_ready_i;

  // Pack AXI beat into the skid struct (one-cycle entry buffer).
  always_comb begin
    skid_value_d.data             = axis_slave_if.tdata;
    skid_value_d.valid_bytes_mask = axis_slave_if.tkeep;
    skid_value_d.last_byte        = axis_slave_if.tlast;
    skid_value_d.valid_data_i     = axis_slave_if.tvalid;
  end

  always_comb begin
    next_state     = current_state;
    out_data_d     = out_data_o;
    out_control_d  = out_control_o;
    num_incoming_d = num_incoming_q;
    out_valid_d    = 1'b0;
    consume_skid   = 1'b0;
    tready_d       = (!skid_value_q.valid_data_i) || can_read;

    case (current_state)
      // ---------------------------------------------------------------
      // Wait for the first valid AXI beat. Emit IDLEs until then. When
      // the beat lands, emit SOF (pure preamble, no AXI consumed) and
      // hand off to DATA — the held skid will be the first frame block.
      // ---------------------------------------------------------------
      WAIT_START: begin
        if (can_read) begin
          out_control_d = CTRL_HDR;
          out_data_d    = {8'hd5, {6{8'h55}}, SOF_L0};
          out_valid_d   = 1'b1;
          tready_d      = 1'b0;  // hold the skid for DATA next cycle

          if (skid_value_q.last_byte) begin
            // Single-beat frame (rare with 8-byte AXI, but possible) — go
            // straight to EOF. num_incoming captured from the held skid.
            next_state     = EOF;
            num_incoming_d = count_valid(skid_value_q.valid_bytes_mask);
          end else begin
            next_state = DATA;
          end
        end else if (out_ready_i) begin
          out_control_d = CTRL_HDR;
          out_data_d    = {{7{8'h00}}, IDLE_BLK};
          out_valid_d   = 1'b1;
        end
      end

      // ---------------------------------------------------------------
      // Stream full 8-byte DATA blocks until we see a tlast on the
      // newly-fetched beat — that beat is the LAST and is finished off
      // in EOF.
      // ---------------------------------------------------------------
      DATA: begin
        if (can_read) begin
          out_control_d = DATA_HDR;
          out_data_d    = skid_value_q.data;
          out_valid_d   = 1'b1;
          consume_skid  = 1'b1;
        end

        if (next_is_last) begin
          next_state     = EOF;
          num_incoming_d = count_valid(skid_value_d.valid_bytes_mask);
        end
      end

      // ---------------------------------------------------------------
      // Emit the trailing TERM block (and possibly one preceding DATA
      // block if the last beat was full-width). num_incoming_q = number
      // of valid bytes in the held last beat.
      // ---------------------------------------------------------------
      EOF: begin
        if (out_ready_i) begin
          if (num_incoming_q == 4'd8) begin
            // Last beat is full: emit it as DATA, then TERM_L0 next cycle.
            out_control_d  = DATA_HDR;
            out_data_d     = skid_value_q.data;
            out_valid_d    = 1'b1;
            consume_skid   = 1'b1;
            num_incoming_d = 4'd0;
            tready_d       = 1'b0;
          end else begin
            out_control_d = CTRL_HDR;
            out_valid_d   = 1'b1;
            unique case (num_incoming_q)
              4'd0: out_data_d = {{7{8'h00}},                                     TERM_L0};
              4'd1: out_data_d = {{6{8'h00}}, skid_value_q.data[0 +: 1*BYTE_W],   TERM_L1};
              4'd2: out_data_d = {{5{8'h00}}, skid_value_q.data[0 +: 2*BYTE_W],   TERM_L2};
              4'd3: out_data_d = {{4{8'h00}}, skid_value_q.data[0 +: 3*BYTE_W],   TERM_L3};
              4'd4: out_data_d = {{3{8'h00}}, skid_value_q.data[0 +: 4*BYTE_W],   TERM_L4};
              4'd5: out_data_d = {{2{8'h00}}, skid_value_q.data[0 +: 5*BYTE_W],   TERM_L5};
              4'd6: out_data_d = {{1{8'h00}}, skid_value_q.data[0 +: 6*BYTE_W],   TERM_L6};
              4'd7: out_data_d =              {skid_value_q.data[0 +: 7*BYTE_W],  TERM_L7};
              default: out_data_d = {{7{8'h00}}, TERM_L0};
            endcase
            if (num_incoming_q != 4'd0) consume_skid = 1'b1;
            next_state = IDLE_OUT;
            tready_d   = 1'b0;
          end
        end
      end

      // ---------------------------------------------------------------
      // Force at least one IDLE between TERM and the next SOF so the
      // receiver's IPG counter accumulates.
      // ---------------------------------------------------------------
      IDLE_OUT: begin
        tready_d = 1'b0;
        if (out_ready_i) begin
          next_state    = WAIT_START;
          out_control_d = CTRL_HDR;
          out_data_d    = {{7{8'h00}}, IDLE_BLK};
          out_valid_d   = 1'b1;
        end
      end

      default: next_state = WAIT_START;
    endcase
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      current_state  <= WAIT_START;
      skid_value_q   <= '0;
      num_incoming_q <= '0;
    end else begin
      current_state  <= next_state;
      num_incoming_q <= num_incoming_d;

      if (get_axi) begin
        skid_value_q <= skid_value_d;
      end else if (consume_skid) begin
        skid_value_q.valid_data_i <= 1'b0;
      end
    end
  end

  // Combinational tready — registering it would let the upstream push a beat
  // into a still-full skid.
  assign axis_slave_if.tready = tready_d;

  data_pipeline #(.DATA_W(DATA_W),    .PIPE_DEPTH(PIPE_DEPTH), .RST_EN(0))
      pipe_data    (.clk(clk), .rst(rst), .data_i(out_data_d),    .data_o(out_data_o));
  data_pipeline #(.DATA_W(CONTROL_W), .PIPE_DEPTH(PIPE_DEPTH), .RST_EN(0))
      pipe_control (.clk(clk), .rst(rst), .data_i(out_control_d), .data_o(out_control_o));
  data_pipeline #(.DATA_W(1),         .PIPE_DEPTH(PIPE_DEPTH), .RST_EN(1))
      pipe_valid   (.clk(clk), .rst(rst), .data_i(out_valid_d),   .data_o(out_valid_o));

endmodule : pcs_generator
