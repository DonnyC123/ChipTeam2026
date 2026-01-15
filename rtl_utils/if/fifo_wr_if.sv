interface fifo_wr_if #(
  parameter DATA_W = 32
);

  logic [DATA_W-1:0]  data;
  logic               wr_en;
  logic               full;

  modport slave (
    input   wr_en,
    input   data,
    output  full
  );

  modport master (
    output  wr_en,
    output  data,
    input   full 
  );

endinterface