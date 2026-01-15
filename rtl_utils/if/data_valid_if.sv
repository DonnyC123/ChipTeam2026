interface data_valid_if #(
  parameter int DATA_W = 8
);

  logic [DATA_W-1:0]  data;
  logic               valid;

  modport slave (
    input data,
    input valid
  );

  modport master (
    output data,
    output valid
  );

endinterface