# TX Full-Chain Testbench

`TX/tb` is the cocotb full-chain testbench

## DUT Path

The testbench wrapper is `TX/tx_top.sv`:

```text
DMA AXIS -> tx_subsystem -> crc_inserter -> pcs_generator
         -> scrambler -> debubbler -> raw 64b stream
```

The runner compiles the normalized RTL under `TX/rtl`, excludes standalone PCS
test tops, then adds `TX/tx_top.sv`.

## Running

From the repository root:

```sh
~/miniconda3/bin/python TX/tb/tx_tb_runner.py
```

Useful environment variables:

```sh
COCOTB_WAVES=0 ~/miniconda3/bin/python TX/tb/tx_tb_runner.py
TX_TB_NUM_QUEUES=2 TX_TB_FIFO_DEPTH=16 ~/miniconda3/bin/python TX/tb/tx_tb_runner.py
TX_TB_MAX_BURST_BEATS=128 ~/miniconda3/bin/python TX/tb/tx_tb_runner.py
```

`TX_TB_NUM_QUEUES`, `TX_TB_FIFO_DEPTH`, and `TX_TB_MAX_BURST_BEATS` are passed
to both the SystemVerilog top parameters and the Python stimulus code, so
`tdest` width stays aligned with the RTL configuration.

## Coverage

The tests cover minimum and long frames, all DMA tail `tkeep` widths,
back-to-back packets with and without idle cycles, randomized ingress gaps,
multi-queue tagged payloads, FIFO pressure/backpressure, and queue-width
configuration. The scoreboard descrambles and decodes the final debubbled raw
stream using a permissive RX-style payload search. A lightweight PCS 66b checker
also monitors `pcs_data_o`, `pcs_control_o`, and `pcs_valid_o`.
