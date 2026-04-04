package median_filter_pkg;

  localparam int KERNEL_LEN = 2;
  localparam int PIXEL_W    = 8;


  typedef struct packed {
    logic [PIXEL_W-1:0] red;
    logic [PIXEL_W-1:0] green;
    logic [PIXEL_W-1:0] blue;
  } pixel_t;

  // Takes: two logic values of PIXEL_W {a,b}
  // Function: swaps if a > b
  // Returns: the potentially swapped values {a,b} || {b,a}
  function automatic logic [2*PIXEL_W-1:0] swap(
      input logic [PIXEL_W-1:0] a,
      input logic [PIXEL_W-1:0] b
  );
      if (a <= b) return {a, b};
      else        return {b, a};
  endfunction

  // Takes: 4 logic values of PIXEL_W (r || g || b)
  // Function: Sorts those values
  // Returns: the middle two of those sorted values appended together
  function automatic logic [2*PIXEL_W-1:0] get_middle_values (logic [PIXEL_W-1:0] value1, logic [PIXEL_W-1:0] value2, 
    logic [PIXEL_W-1:0] value3, logic [PIXEL_W-1:0] value4);
    logic [PIXEL_W-1:0] a,b,c,d;
    logic [2*PIXEL_W-1:0] swapped_vals;

    // start
    a = value1; b = value2; c = value3; d = value4;
    // (a,b)
    swapped_vals = swap(a,b); 
    a = swapped_vals[2*PIXEL_W-1 -: PIXEL_W]; 
    b = swapped_vals[PIXEL_W-1:0];
    // (c,d)
    swapped_vals = swap(c,d); 
    c = swapped_vals[2*PIXEL_W-1 -: PIXEL_W]; 
    d = swapped_vals[PIXEL_W-1:0];
    // (a,c)
    swapped_vals = swap(a,c); 
    a = swapped_vals[2*PIXEL_W-1 -: PIXEL_W]; 
    c = swapped_vals[PIXEL_W-1:0];
    // (b,d)
    swapped_vals = swap(b,d); 
    b = swapped_vals[2*PIXEL_W-1 -: PIXEL_W]; 
    d = swapped_vals[PIXEL_W-1:0];
    // (b,c)
    swapped_vals = swap(b,c); 
    b = swapped_vals[2*PIXEL_W-1 -: PIXEL_W]; 
    c = swapped_vals[PIXEL_W-1:0];

    return {b, c}; // sorted so take middle
  endfunction

  
  // Takes: two pixel values rgb values appended together
  // Function: does the adverage
  // Returns: the adverage
  function automatic logic [PIXEL_W-1:0] get_adverage (logic [PIXEL_W*2-1:0] values);
    // add and divide by 2
    logic [PIXEL_W-1:0] sum;
    sum = values[2*PIXEL_W-1 -: PIXEL_W] + values[PIXEL_W-1:0];
    return sum / 2;
  endfunction

endpackage
