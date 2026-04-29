interface axi_stream_if #(
    parameter DATA_W = 256
);

  localparam MASK_W = $clog2(DATA_W);

  logic [DATA_W-1:0] data;
  logic [MASK_W-1:0] mask;
  logic              valid;
  logic              last;
  logic              ready;

  modport master(  //
      output data,
      output mask,
      output valid,
      output last,
      input ready
  );

  modport slave(  //

      input data,
      input mask,
      input valid,
      input last,
      output ready
  );


endinterface
