package parser_pkg;

localparam IPV4_CODE = 16'h0008; 
localparam IPV6_CODE = 16'hDD86; 

typedef enum logic [2:0] {IPV4, IPV6, OTHER} outputs_t;

endpackage