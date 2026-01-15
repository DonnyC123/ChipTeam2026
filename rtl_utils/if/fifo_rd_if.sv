interface fifo_rd_if #(
    parameter DATA_W = 32
);

  logic [DATA_W-1:0] data;
  logic              rd_en;
  logic              empty;

  modport slave(input rd_en, output data, output empty);

  modport master(output rd_en, input data, input empty);

endinterface

