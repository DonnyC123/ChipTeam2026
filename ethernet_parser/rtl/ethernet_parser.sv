import parser_pkg::*;

module ethernet_parser #(
    parameter DATA_IN_W  = 64,
    parameter BYTES_OUT  = DATA_IN_W / 8
)(
    input logic                 clk,
    input logic                 rst,
    input logic                 data_valid_i,
    input logic [DATA_IN_W-1:0] data_i,
    input logic [BYTES_OUT-1:0] bytes_valid_i,

    output logic                sof_type_o,
    output logic                payload_time_o,
    output logic                valid_o,

    output outputs_t            outputs_o
);

typedef enum logic [3:0] {IDLE, PAUSE, PARSE_L4, PARSE_L0} state_t;

state_t current_state, next_state;


outputs_t outputs_d, outputs_q;

logic valid_d;
logic payload_time_d;

logic sof_or_eof_d, sof_or_eof_q;
logic sof_type_d;

logic [$bits(outputs_t)-1:0] pipeline_outputs_raw;
always_comb begin
    // defaults
    next_state       = current_state;
    outputs_d        = outputs_q;
    valid_d          = 1'b0;
    payload_time_d   = 1'b0;
    sof_type_d       = 1'b0;
    sof_or_eof_d     = sof_or_eof_q;

    case (current_state)

        IDLE: begin
            if (data_valid_i) begin
                if (bytes_valid_i == 8'hFE && !sof_or_eof_q) begin
                    sof_or_eof_d = 1'b1;
                    next_state   = PAUSE;
                end
                else if (bytes_valid_i == 8'hF7 && !sof_or_eof_q) begin
                    sof_or_eof_d = 1'b1;
                    next_state   = PARSE_L4;
                end
            end
        end

        PAUSE: begin
            if (data_valid_i) begin
                next_state = PARSE_L0;
            end
        end

        PARSE_L0: begin
            if (data_valid_i) begin
                valid_d        = 1'b1;
                payload_time_d = 1'b1;
                next_state     = IDLE;

                if (data_i[23-:16] == IPV4)
                    outputs_d = IPV4;
                else if (data_i[23-:16] == IPV6)
                    outputs_d = IPV6;
            end
        end

        PARSE_L4: begin
            if (data_valid_i) begin
                valid_d        = 1'b1;
                payload_time_d = 1'b1;
                next_state     = IDLE;

                if (data_i[56-:16] == IPV4)
                    outputs_d = IPV4;
                else if (data_i[56-:16] == IPV6)
                    outputs_d = IPV6;
            end
        end

    endcase
end

always_ff @(posedge clk) begin
    if (rst) begin
        current_state   <= IDLE;
        sof_or_eof_q    <= 1'b0;
        outputs_q <= IPV4;
    end else begin
        current_state   <= next_state;
        sof_or_eof_q    <= sof_or_eof_d;
        outputs_q       <= outputs_d;
    end
end

// pipelines

data_pipeline #(
    .DATA_W(1),
    .PIPE_DEPTH(1),
    .RST_EN(1),
    .RST_VAL(0)
) pipeline_valid (
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
) pipeline_payload (
    .clk(clk),
    .rst(rst),
    .data_i(payload_time_d),
    .data_o(payload_time_o)
);

data_pipeline #(
    .DATA_W($bits(outputs_t)),
    .PIPE_DEPTH(1),
    .RST_EN(0)
) pipeline_outputs (
    .clk    (clk),
    .rst    (rst),
    .data_i (logic'(outputs_d)),
    .data_o (pipeline_outputs_raw)
);

assign outputs_o = outputs_t'(pipeline_outputs_raw);

data_pipeline #(
    .DATA_W(1),
    .PIPE_DEPTH(1),
    .RST_EN(0)
) pipeline_sof (
    .clk(clk),
    .rst(rst),
    .data_i(sof_type_d),
    .data_o(sof_type_o)
);

endmodule