module tx_subsystem import tx_subsystem_pkg::*; #(
    parameter int FIFO_DEPTH = 64,
    parameter int DESC_DEPTH = 32
) (
    input  logic                   dma_clk,
    input  logic                   dma_rst,
    input  logic [DMA_DATA_W-1:0]  s_axis_dma_tdata_i,
    input  logic [DMA_VALID_W-1:0] s_axis_dma_tkeep_i,
    input  logic                   s_axis_dma_tvalid_i,
    input  logic                   s_axis_dma_tlast_i,
    output logic                   s_axis_dma_tready_o,

    input  logic                   tx_clk,
    input  logic                   tx_rst,
    output logic [PCS_DATA_W-1:0]  m_axis_pcs_tdata_o,
    output logic [PCS_VALID_W-1:0] m_axis_pcs_tkeep_o,
    output logic                   m_axis_pcs_tvalid_o,
    output logic                   m_axis_pcs_tlast_o,
    input  logic                   m_axis_pcs_tready_i
);

  localparam int WORD_CNT_W = (FIFO_DEPTH > 1) ? $clog2(FIFO_DEPTH + 1) : 1;
  localparam int LANE_W     = (BEATS_PER_ENTRY > 1) ? $clog2(BEATS_PER_ENTRY) : 1;

  logic [FIFO_ENTRY_W-1:0] data_wr_payload;
  logic [FIFO_ENTRY_W-1:0] data_rd_payload;
  logic                    data_wr_valid;
  logic                    data_wr_ready;
  logic                    data_rd_valid;
  logic                    data_rd_ready;
  logic                    data_fifo_full;
  logic                    data_fifo_empty;

  logic [WORD_CNT_W-1:0] desc_wr_payload;
  logic [WORD_CNT_W-1:0] desc_rd_payload;
  logic                  desc_wr_valid;
  logic                  desc_wr_ready;
  logic                  desc_rd_valid;
  logic                  desc_rd_ready;
  logic                  desc_fifo_full;
  logic                  desc_fifo_empty;

  fifo_entry_t data_rd_entry;

  logic [WORD_CNT_W-1:0] dma_packet_words_q, dma_packet_words_d;
  logic                  axis_accept;

  logic [DMA_DATA_W-1:0]  word_data_q, word_data_d;
  logic [DMA_VALID_W-1:0] word_keep_q, word_keep_d;
  logic                   word_last_q, word_last_d;
  logic                   word_valid_q, word_valid_d;
  logic [LANE_W-1:0]      lane_idx_q, lane_idx_d;
  logic [LANE_W-1:0]      terminal_lane_q, terminal_lane_d;
  logic                   packet_active_q, packet_active_d;
  logic [WORD_CNT_W-1:0]  words_remaining_q, words_remaining_d;

  logic desc_accept;
  logic load_word;
  logic output_accept;
  logic output_terminal_lane;

  function automatic logic [LANE_W-1:0] terminal_lane_from_keep(
      input logic [DMA_VALID_W-1:0] keep,
      input logic                   last
  );
    logic [PCS_VALID_W-1:0] lane_keep;
    begin
      terminal_lane_from_keep = LANE_W'(BEATS_PER_ENTRY - 1);
      if (last) begin
        terminal_lane_from_keep = '0;
        for (int i = 0; i < BEATS_PER_ENTRY; i++) begin
          lane_keep = keep[i * PCS_VALID_W +: PCS_VALID_W];
          if (lane_keep != '0) begin
            terminal_lane_from_keep = LANE_W'(i);
          end
        end
      end
    end
  endfunction

  assign axis_accept        = s_axis_dma_tvalid_i && s_axis_dma_tready_o;
  assign data_wr_payload    = {s_axis_dma_tdata_i, s_axis_dma_tkeep_i, s_axis_dma_tlast_i};
  assign desc_wr_payload    = dma_packet_words_q + WORD_CNT_W'(1);
  assign data_wr_valid      = axis_accept;
  assign desc_wr_valid      = axis_accept && s_axis_dma_tlast_i;
  assign s_axis_dma_tready_o = !dma_rst && data_wr_ready &&
                               (!s_axis_dma_tlast_i || desc_wr_ready);

  tx_async_fifo #(
      .DATA_W(FIFO_ENTRY_W),
      .DEPTH (FIFO_DEPTH)
  ) data_fifo (
      .wr_clk_i  (dma_clk),
      .wr_rst_i  (dma_rst),
      .wr_data_i (data_wr_payload),
      .wr_valid_i(data_wr_valid),
      .wr_ready_o(data_wr_ready),
      .wr_full_o (data_fifo_full),
      .rd_clk_i  (tx_clk),
      .rd_rst_i  (tx_rst),
      .rd_data_o (data_rd_payload),
      .rd_valid_o(data_rd_valid),
      .rd_ready_i(data_rd_ready),
      .rd_empty_o(data_fifo_empty)
  );

  tx_async_fifo #(
      .DATA_W(WORD_CNT_W),
      .DEPTH (DESC_DEPTH)
  ) desc_fifo (
      .wr_clk_i  (dma_clk),
      .wr_rst_i  (dma_rst),
      .wr_data_i (desc_wr_payload),
      .wr_valid_i(desc_wr_valid),
      .wr_ready_o(desc_wr_ready),
      .wr_full_o (desc_fifo_full),
      .rd_clk_i  (tx_clk),
      .rd_rst_i  (tx_rst),
      .rd_data_o (desc_rd_payload),
      .rd_valid_o(desc_rd_valid),
      .rd_ready_i(desc_rd_ready),
      .rd_empty_o(desc_fifo_empty)
  );

  assign {data_rd_entry.data, data_rd_entry.valid, data_rd_entry.last} = data_rd_payload;

  assign desc_rd_ready       = !packet_active_q && !word_valid_q;
  assign desc_accept         = desc_rd_valid && desc_rd_ready;
  assign output_accept       = word_valid_q && m_axis_pcs_tready_i;
  assign output_terminal_lane = output_accept && (lane_idx_q == terminal_lane_q);
  assign data_rd_ready       = packet_active_q && (words_remaining_q != '0) &&
                               (!word_valid_q || output_terminal_lane);
  assign load_word           = data_rd_valid && data_rd_ready;

  assign m_axis_pcs_tvalid_o = word_valid_q;
  assign m_axis_pcs_tdata_o  = word_data_q[lane_idx_q * PCS_DATA_W +: PCS_DATA_W];
  assign m_axis_pcs_tkeep_o  = word_keep_q[lane_idx_q * PCS_VALID_W +: PCS_VALID_W];
  assign m_axis_pcs_tlast_o  = word_valid_q && word_last_q && (lane_idx_q == terminal_lane_q);

  always_comb begin
    dma_packet_words_d = dma_packet_words_q;
    if (axis_accept) begin
      if (s_axis_dma_tlast_i) begin
        dma_packet_words_d = '0;
      end else begin
        dma_packet_words_d = dma_packet_words_q + WORD_CNT_W'(1);
      end
    end
  end

  always_comb begin
    word_data_d       = word_data_q;
    word_keep_d       = word_keep_q;
    word_last_d       = word_last_q;
    word_valid_d      = word_valid_q;
    lane_idx_d        = lane_idx_q;
    terminal_lane_d   = terminal_lane_q;
    packet_active_d   = packet_active_q;
    words_remaining_d = words_remaining_q;

    if (desc_accept) begin
      packet_active_d   = 1'b1;
      words_remaining_d = desc_rd_payload;
    end

    if (output_accept) begin
      if (lane_idx_q == terminal_lane_q) begin
        word_valid_d = 1'b0;
        lane_idx_d   = '0;
        if (word_last_q) begin
          packet_active_d = 1'b0;
        end
      end else begin
        lane_idx_d = lane_idx_q + LANE_W'(1);
      end
    end

    if (load_word) begin
      word_data_d       = data_rd_entry.data;
      word_keep_d       = data_rd_entry.valid;
      word_last_d       = data_rd_entry.last;
      word_valid_d      = 1'b1;
      lane_idx_d        = '0;
      terminal_lane_d   = terminal_lane_from_keep(data_rd_entry.valid, data_rd_entry.last);
      words_remaining_d = words_remaining_q - WORD_CNT_W'(1);
    end
  end

  always_ff @(posedge dma_clk) begin
    if (dma_rst) begin
      dma_packet_words_q <= '0;
    end else begin
      dma_packet_words_q <= dma_packet_words_d;
    end
  end

  always_ff @(posedge tx_clk) begin
    if (tx_rst) begin
      word_data_q       <= '0;
      word_keep_q       <= '0;
      word_last_q       <= 1'b0;
      word_valid_q      <= 1'b0;
      lane_idx_q        <= '0;
      terminal_lane_q   <= '0;
      packet_active_q   <= 1'b0;
      words_remaining_q <= '0;
    end else begin
      word_data_q       <= word_data_d;
      word_keep_q       <= word_keep_d;
      word_last_q       <= word_last_d;
      word_valid_q      <= word_valid_d;
      lane_idx_q        <= lane_idx_d;
      terminal_lane_q   <= terminal_lane_d;
      packet_active_q   <= packet_active_d;
      words_remaining_q <= words_remaining_d;
    end
  end

endmodule
