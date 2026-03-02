module tx_subsystem #(
    parameter int DMA_DATA_W  = 256,
    parameter int DMA_VALID_W = 32,
    parameter int PCS_DATA_W  = 64,
    parameter int PCS_VALID_W = 8,
    parameter int FIFO_DEPTH  = 32,
    parameter int NUM_QUEUES  = 2
) (
    input  logic                              clk,
    input  logic                              rst,
    input  logic [DMA_DATA_W-1:0]             dma_data_i,
    input  logic [DMA_VALID_W-1:0]            dma_valid_i,
    input  logic [NUM_QUEUES-1:0]             q_valid_i,
    input  logic [NUM_QUEUES-1:0]             q_last_i,
    output logic                              dma_read_en_o,
    output logic [$clog2(NUM_QUEUES)-1:0]     dma_queue_sel_o,
    output logic [PCS_DATA_W-1:0]             pcs_data_o,
    output logic [PCS_VALID_W-1:0]            pcs_valid_o,
    input  logic                              pcs_read_i
);

  logic fifo_empty;
  logic fifo_full;
  logic fifo_req;
  logic fifo_grant;
  logic dma_wr_en;

  assign dma_wr_en  = dma_read_en_o;
  assign fifo_grant = fifo_req && !fifo_full;

  tx_fifo #(
      .DMA_DATA_W  (DMA_DATA_W),
      .DMA_VALID_W (DMA_VALID_W),
      .PCS_DATA_W  (PCS_DATA_W),
      .PCS_VALID_W (PCS_VALID_W),
      .DEPTH       (FIFO_DEPTH)
  ) tx_fifo_inst (
      .clk          (clk),
      .rst          (rst),
      .dma_data_i   (dma_data_i),
      .dma_valid_i  (dma_valid_i),
      .dma_wr_en_i  (dma_wr_en),
      .pcs_data_o   (pcs_data_o),
      .pcs_valid_o  (pcs_valid_o),
      .pcs_read_i   (pcs_read_i),
      .empty_o      (fifo_empty),
      .full_o       (fifo_full),
      .sched_req_i  (fifo_req),
      .sched_grant_o(fifo_grant)
  );

  tx_scheduling #(
      .NUM_QUEUES (NUM_QUEUES)
  ) tx_scheduling_inst (
      .clk            (clk),
      .rst            (rst),
      .q_valid_i      (q_valid_i),
      .q_last_i       (q_last_i),
      .fifo_full_i    (fifo_full),
      .fifo_grant_i   (fifo_grant),
      .dma_read_en_o  (dma_read_en_o),
      .dma_queue_sel_o(dma_queue_sel_o),
      .fifo_req_o     (fifo_req)
  );

endmodule
