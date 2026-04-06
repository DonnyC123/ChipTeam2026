interface pixel_valid_if ();
  import median_filter_pkg::pixel_t;

  pixel_t pixel;
  logic   valid;

  modport master(  //
      output pixel,
      output valid
  );

  modport slave(  //
      input pixel,
      input valid
  );

endinterface
