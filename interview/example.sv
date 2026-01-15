module example ();

  wire a;
  wire b;
  wire sel;
  wire out_d;
  wire out_q;

  assign out_d = sel ? a : b;

  always @(posedge clk) begin
    if (rst) begin
      out_q <= '0;
    end else begin
      out_q <= out_d;
    end
  end

endmodule
