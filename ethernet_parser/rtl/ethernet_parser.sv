import parser_pkg::*;

module ethernet_parser #(
    parameter DATA_IN_W  = 64,
    parameter BYTES_OUT  = DATA_IN_W / SIZE_BYTE,
    localparam SIZE_BYTE = 8
)(
    input logic                 clk,
    input logic                 rst,
    input logic                 data_valid_i,
    input logic [DATA_IN_W-1:0] data_i,
    input logic [BYTES_OUT-1:0] bytes_valid_i,

    // output logic ipv4_o,
    // output logic ipv6_o,
    // output logic other_o,
    output logic payload_time_o, //high when payload
    output logic valid_o,
    output       outputs_t outputs_o //theres got to be a way to make one enum outport, idk if its it
);

typedef enum logic [3:0] {IDLE, PAUSE, PARSE_L4, PARSE_L0} state_t;

outputs_t outputs_d;
state_t current_state, next_state;

logic valid_d;
logic payload_time_d;

always_comb begin
    //defaults
    outputs_d      = outputs_q; 
    payload_time_d = '0;
    valid_d        = '0;
    next_state     = current_state;

    case(current_state)
        IDLE : begin 
            if(data_valid_i) begin
                next_state = (bytes_valid_i == 8'h07) ? PARSE_L4 : PAUSE; //0000_0111
            end
        end

        PAUSE : begin
            if(data_valid_i) begin
                next_state = PARSE_L0; 
            end
        end

        PARSE_L0 : begin 
            if(data_valid_i) begin
                next_state     = IDLE;
                payload_time_d = 1'b1;
                valid_d        = 1'b1;
                if (data_i[23-:SIZE_BYTE*2] == IPV4) begin
                    outputs_d = IPV4;
                end else if (data_i[23-:SIZE_BYTE*2] == IPV6) begin
                    outputs_d = IPV6;
                end
            end 
        end

        PARSE_L4 : begin 
            if(data_valid_i) begin
                next_state     = IDLE;
                payload_time_d = 1'b1;
                valid_d        = 1'b1;
                if (data_i[56-:SIZE_BYTE*2] == IPV4) begin
                    outputs_d = IPV4;
                end else if (data_i[56-:SIZE_BYTE*2] == IPV6) begin
                    outputs_d = IPV6;
                end
            end  
        end
    endcase
end

always_ff begin 
    if(rst) begin
        current_state = IDLE;
    end else begin
        current_state = next_state;
    end
end

data_pipeline #(
    .DATA_W(1),
    .PIPE_DEPTH(1),
    .RST_EN(1),
    .RST_VAL(0)
) pipeline_1 (
    .clk(clk),
    .rst(rst),
    .data_i(valid_d),
    .data_o(valid_o)
);

data_pipeline #(
    .DATA_W(1),
    .PIPE_DEPTH(1),
    .RST_EN(1),
    .RST_VAL(0)
) pipeline_2 (
    .clk(clk),
    .rst(rst),
    .data_i(payload_time_d),
    .data_o(payload_time_o)
);

data_pipeline #(
    .DATA_W(1),
    .PIPE_DEPTH(1),
    .RST_EN(0)
) pipeline_3 (
    .clk(clk),
    .rst(rst),
    .data_i(outputs_d),
    .data_o(outputs_o)
);
    
endmodule : ethernet_parser