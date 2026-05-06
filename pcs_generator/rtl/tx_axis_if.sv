interface tx_axis_if #(
    parameter int DATA_W = 64,
    parameter int KEEP_W = DATA_W / 8,
    parameter int DEST_W = 1
);
  logic [DATA_W-1:0] tdata;
  logic [KEEP_W-1:0] tkeep;
  logic              tvalid;
  logic              tready;
  logic              tlast;
  logic [DEST_W-1:0] tdest;

  modport master (
      output tdata,
      output tkeep,
      output tvalid,
      output tlast,
      output tdest,
      input  tready
  );

  modport slave (
      input  tdata,
      input  tkeep, //this is bytes mask
      input  tvalid,
      input  tlast,
      input  tdest, //this is tied to nothing
      output tready //we can get data from FIFO
  );

endinterface