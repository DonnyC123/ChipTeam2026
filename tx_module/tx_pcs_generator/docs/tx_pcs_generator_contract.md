# TX PCS Generator Contract (25GBASE-R 64b/66b Normal Data Path)

This module converts AXI-Stream frame bytes into 64b/66b blocks for the TX pipeline.

## Interface Semantics

- `in_*` is AXI-Stream payload input:
  - `in_data_i[63:0]`
  - `in_keep_i[7:0]`
  - `in_last_i`
  - `in_valid_i`
  - `in_ready_o`
- `out_*` is 64b/66b block output:
  - `out_control_o[1:0]` is **sync header**
    - `2'b01`: data block
    - `2'b10`: control block
  - `out_data_o[63:0]` is 66b payload bits `[65:2]`
  - `out_valid_o`/`out_ready_i` use ready/valid handshake

## Block Encoding

- Idle control block:
  - Header: `10`
  - Block type byte: `0x1E`
- Start block:
  - Header: `10`
  - Block type byte: `0x78` (S0)
  - Bytes 1..7 are frame data bytes 0..6
- Data block:
  - Header: `01`
  - Payload bytes 0..7 are frame data bytes
- Terminate block:
  - Header: `10`
  - Block type values:
    - `T0=0x87, T1=0x99, T2=0xAA, T3=0xB4`
    - `T4=0xCC, T5=0xD2, T6=0xE1, T7=0xFF`
  - Control-byte lanes are filled with idle control code `0x00`

Lane mapping is little-endian:
- lane0 -> `out_data_o[7:0]`
- lane7 -> `out_data_o[63:56]`

## Input Rules Enforced

- Non-last accepted beat must use `in_keep_i == 8'hFF`
- Last accepted beat must satisfy:
  - `in_keep_i != 8'h00`
  - `in_keep_i` is LSB-contiguous

## Continuous Stream Behavior

- With no frame bytes available, module emits idle control blocks.
- During `out_valid_o && !out_ready_i`, `out_control_o/out_data_o` remain stable.

## Integration Notes (Team Contract)

- Scrambler consumes `out_data_o[63:0]` payload path.
- Sync header (`out_control_o[1:0]`) is carried on control sideband to downstream gearbox/debubbler path.
- Downstream must interpret `{out_control_o, out_data_o}` using the same block-type table above.
