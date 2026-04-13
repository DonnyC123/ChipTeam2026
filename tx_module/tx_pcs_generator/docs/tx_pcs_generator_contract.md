# TX PCS Generator Contract (25GBASE-R 64b/66b Normal Data Path)

This module converts AXI-Stream frame bytes into 64b/66b blocks for the TX pipeline.

## Interface Semantics

- `in_*` is AXI-Stream payload input:
  - `in_data_i[63:0]`
  - `in_keep_i[7:0]`
  - `in_last_i`
  - `in_valid_i`
  - `in_ready_o`
- `out_*` is 64b/66b block output toward scrambler/debubbler path:
  - `out_control_o[1:0]` is **sync header**
    - `2'b01`: data block
    - `2'b10`: control block
  - `out_data_o[63:0]` is 66b payload bits `[65:2]`
  - `out_valid_o`/`out_ready_i` use ready/valid handshake

## TX Chain Integration Contract

- PCS -> Scrambler signals: `out_control_o[1:0]`, `out_data_o[63:0]`, `out_valid_o`.
- If downstream logic has no backpressure support, tie `out_ready_i` to `1'b1`.
- Scrambler is expected to scramble **payload** (`out_data_o`) only.
- Sync header (`out_control_o`) is sideband and must stay aligned with the corresponding payload block.
- Downstream gearbox/debubbler interpretation must use `{sync_header, payload64}` of the same cycle.

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
- This S0-only implementation requires minimum frame length `>= 7` bytes.
  Short frames (`<7` bytes) are treated as illegal input and trigger assertion in simulation.

## Continuous Stream and Stall Behavior

- With no frame bytes available, module emits idle control blocks.
- During `out_valid_o && !out_ready_i`, `out_control_o/out_data_o` remain stable.
- While in-frame, if buffered bytes are temporarily insufficient to legally emit next block,
  the module waits for more input bytes (`out_valid_o` may deassert) and does not drop frame state.

## Integration Notes (Team Contract)

- Downstream must interpret `{out_control_o, out_data_o}` using the same block-type table above.
- This module does not generate ordered sets/fault blocks in current scope.
