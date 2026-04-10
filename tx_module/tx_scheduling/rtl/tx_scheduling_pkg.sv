package tx_scheduling_pkg;

  localparam int NUM_QUEUES  = 4;
  localparam int QUEUE_ID_W  = NUM_QUEUES > 1 ? $clog2(NUM_QUEUES) : 1;

  typedef enum logic {
    IDLE,
    SERVING
  } state_t;

  typedef struct packed {
    logic [QUEUE_ID_W-1:0] queue_id;
    logic                  valid;
  } dma_req_t;

  localparam int DMA_REQ_W = $bits(dma_req_t);

endpackage
