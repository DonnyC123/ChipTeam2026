package parser_pkg;

localparam IPV4_CODE = 16'h0800; 
localparam IPV6_CODE = 16'h86DD; 

typedef enum logic [2:0] {IPV4, IPV6, OTHER} outputs_t;

endpackage