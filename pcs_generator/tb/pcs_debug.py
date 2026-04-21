from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

from cocotb.utils import get_sim_time


STATE_NAMES = {
    0: "WAIT_START",
    1: "DATA",
    2: "EOF",
    3: "IDLE_OUT",
}

TRACE_HISTORY_DEPTH = 16
HEX_LINE_WIDTH = 16
WINDOW_RADIUS = 8


def logic_to_int(value: Any) -> int:
    if isinstance(value, int):
        return value

    return int(value)


def logic_to_int_or_none(value: Any) -> Optional[int]:
    try:
        return logic_to_int(value)
    except (TypeError, ValueError):
        return None


def current_time_ns() -> int:
    return int(get_sim_time("ns"))


def format_hex_byte(byte_value: int) -> str:
    return f"0x{byte_value:02X}"


def format_bytes_inline(payload: bytes) -> str:
    if not payload:
        return "<empty>"
    return " ".join(f"{byte_value:02X}" for byte_value in payload)


def format_hexdump(payload: bytes, *, width: int = HEX_LINE_WIDTH) -> str:
    if not payload:
        return "0000: <empty>"

    lines = []
    for offset in range(0, len(payload), width):
        chunk = payload[offset : offset + width]
        hex_bytes = " ".join(f"{byte_value:02X}" for byte_value in chunk)
        lines.append(f"{offset:04X}: {hex_bytes}")
    return "\n".join(lines)


def first_payload_difference(expected: bytes, actual: bytes) -> Optional[int]:
    common_len = min(len(expected), len(actual))
    for byte_index in range(common_len):
        if expected[byte_index] != actual[byte_index]:
            return byte_index

    if len(expected) != len(actual):
        return common_len

    return None


def format_payload_window(payload: bytes, center_index: int, *, radius: int = WINDOW_RADIUS) -> str:
    if not payload:
        return "<empty>"

    center_index = max(0, min(center_index, len(payload) - 1))
    window_start = max(0, center_index - radius)
    window_end = min(len(payload), center_index + radius + 1)
    window = payload[window_start:window_end]
    rendered = []
    for offset, byte_value in enumerate(window, start=window_start):
        marker = ">>" if offset == center_index else "  "
        rendered.append(f"{marker}{offset:04X}:{byte_value:02X}")
    return " ".join(rendered)


def indent_block(text: str, prefix: str = "    ") -> str:
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


def format_recent_records(records: Sequence[Any], *, empty_message: str) -> str:
    if not records:
        return empty_message
    return "\n".join(record.describe() for record in records)


def bounded_trace(records: Iterable[Any], *, depth: int = TRACE_HISTORY_DEPTH) -> tuple[Any, ...]:
    return tuple(deque(records, maxlen=depth))


@dataclass(frozen=True)
class AxiActivityRecord:
    activity_index: int
    sim_time_ns: int
    idle: bool
    tvalid: int
    tkeep: int
    tlast: int
    out_ready: int
    valid_bytes: bytes
    contributes_payload: bool

    def describe(self) -> str:
        contribution = "payload" if self.contributes_payload else "context"
        return (
            f"activity[{self.activity_index}] @{self.sim_time_ns}ns "
            f"idle={int(self.idle)} tvalid={self.tvalid} "
            f"tkeep=0x{self.tkeep:02X} tlast={self.tlast} "
            f"out_ready={self.out_ready} {contribution}={format_bytes_inline(self.valid_bytes)}"
        )


@dataclass(frozen=True)
class ExpectedFrameRecord:
    frame_index: int
    payload: bytes
    payload_beats: tuple[AxiActivityRecord, ...]
    trace: tuple[AxiActivityRecord, ...]

    def describe(self) -> str:
        return (
            f"expected_frame[{self.frame_index}] len={len(self.payload)} bytes\n"
            f"{indent_block(format_hexdump(self.payload))}"
        )


@dataclass(frozen=True)
class DUTStateSnapshot:
    current_state: Optional[str] = None
    held_byte_cnt: Optional[int] = None
    num_incoming: Optional[int] = None
    axis_tvalid: Optional[int] = None
    axis_tkeep: Optional[int] = None
    axis_tlast: Optional[int] = None
    axis_tready: Optional[int] = None
    out_ready: Optional[int] = None
    can_read: Optional[int] = None
    get_axi: Optional[int] = None
    next_is_last: Optional[int] = None
    skid_valid: Optional[int] = None
    skid_last: Optional[int] = None
    skid_tkeep: Optional[int] = None
    skid_data: Optional[int] = None

    def describe(self) -> str:
        fields = []
        if self.current_state is not None:
            fields.append(f"state={self.current_state}")
        if self.held_byte_cnt is not None:
            fields.append(f"held={self.held_byte_cnt}")
        if self.num_incoming is not None:
            fields.append(f"num_in={self.num_incoming}")
        if self.axis_tvalid is not None:
            fields.append(f"axis_tvalid={self.axis_tvalid}")
        if self.axis_tkeep is not None:
            fields.append(f"axis_tkeep=0x{self.axis_tkeep:02X}")
        if self.axis_tlast is not None:
            fields.append(f"axis_tlast={self.axis_tlast}")
        if self.axis_tready is not None:
            fields.append(f"axis_tready={self.axis_tready}")
        if self.out_ready is not None:
            fields.append(f"out_ready={self.out_ready}")
        if self.can_read is not None:
            fields.append(f"can_read={self.can_read}")
        if self.get_axi is not None:
            fields.append(f"get_axi={self.get_axi}")
        if self.next_is_last is not None:
            fields.append(f"next_is_last={self.next_is_last}")
        if self.skid_valid is not None:
            fields.append(f"skid_valid={self.skid_valid}")
        if self.skid_last is not None:
            fields.append(f"skid_last={self.skid_last}")
        if self.skid_tkeep is not None:
            fields.append(f"skid_tkeep=0x{self.skid_tkeep:02X}")
        if self.skid_data is not None:
            fields.append(f"skid_data=0x{self.skid_data:016X}")

        return " ".join(fields) if fields else "<no DUT snapshot available>"


@dataclass(frozen=True)
class ObservedBlockRecord:
    block_index: int
    sim_time_ns: int
    name: str
    header: int
    raw_data: int
    valid_mask: int
    payload_bytes: bytes
    dut_state: Optional[DUTStateSnapshot]

    def describe(self) -> str:
        dut_snapshot = self.dut_state.describe() if self.dut_state is not None else "<none>"
        return (
            f"block[{self.block_index}] @{self.sim_time_ns}ns {self.name} "
            f"hdr=0b{self.header:02b} valid_mask=0x{self.valid_mask:02X} "
            f"payload={format_bytes_inline(self.payload_bytes)} raw=0x{self.raw_data:016X}\n"
            f"    dut: {dut_snapshot}"
        )


@dataclass(frozen=True)
class ActualFrameRecord:
    frame_index: int
    payload: bytes
    blocks: tuple[ObservedBlockRecord, ...]
    leading_blocks: tuple[ObservedBlockRecord, ...]

    def describe(self) -> str:
        return (
            f"actual_frame[{self.frame_index}] len={len(self.payload)} bytes\n"
            f"{indent_block(format_hexdump(self.payload))}"
        )


def format_frame_mismatch(
    expected_frame: ExpectedFrameRecord, actual_frame: ActualFrameRecord
) -> str:
    mismatch_index = first_payload_difference(expected_frame.payload, actual_frame.payload)
    if mismatch_index is None:
        mismatch_summary = "payloads match"
    elif mismatch_index < len(expected_frame.payload) and mismatch_index < len(actual_frame.payload):
        mismatch_summary = (
            f"first mismatch at byte {mismatch_index}: "
            f"expected {format_hex_byte(expected_frame.payload[mismatch_index])}, "
            f"actual {format_hex_byte(actual_frame.payload[mismatch_index])}"
        )
    elif mismatch_index < len(expected_frame.payload):
        mismatch_summary = (
            f"actual payload ended at byte {mismatch_index}; "
            f"expected trailing byte {format_hex_byte(expected_frame.payload[mismatch_index])}"
        )
    else:
        mismatch_summary = (
            f"actual payload has extra data starting at byte {mismatch_index}: "
            f"{format_hex_byte(actual_frame.payload[mismatch_index])}"
        )

    lines = [
        f"Frame {expected_frame.frame_index} mismatch: {mismatch_summary}",
        f"Expected length={len(expected_frame.payload)}, actual length={len(actual_frame.payload)}",
    ]

    if mismatch_index is not None:
        lines.extend(
            [
                "Expected window:",
                f"  {format_payload_window(expected_frame.payload, mismatch_index)}",
                "Actual window:",
                f"  {format_payload_window(actual_frame.payload, mismatch_index)}",
            ]
        )

    lines.extend(
        [
            "Expected payload hexdump:",
            indent_block(format_hexdump(expected_frame.payload)),
            "Actual payload hexdump:",
            indent_block(format_hexdump(actual_frame.payload)),
            "Expected AXI activity:",
            indent_block(
                format_recent_records(
                    expected_frame.trace,
                    empty_message="<no expected AXI activity recorded>",
                )
            ),
            "Observed PCS blocks before/starting this frame:",
            indent_block(
                format_recent_records(
                    actual_frame.leading_blocks,
                    empty_message="<no leading blocks recorded>",
                )
            ),
            "Observed PCS blocks for this frame:",
            indent_block(
                format_recent_records(
                    actual_frame.blocks,
                    empty_message="<no observed frame blocks recorded>",
                )
            ),
        ]
    )
    return "\n".join(lines)


def format_extra_frames(
    *,
    expected_frames: Sequence[ExpectedFrameRecord],
    actual_frames: Sequence[ActualFrameRecord],
    recent_expected_activity: Sequence[AxiActivityRecord],
    recent_actual_blocks: Sequence[ObservedBlockRecord],
) -> str:
    lines = []
    if expected_frames:
        lines.append(f"Expected queue has {len(expected_frames)} unmatched frame(s).")
        for frame in expected_frames:
            lines.append(frame.describe())
            lines.append("Expected AXI activity for unmatched frame:")
            lines.append(indent_block(format_recent_records(frame.trace, empty_message="<empty>")))

    if actual_frames:
        lines.append(f"Actual queue has {len(actual_frames)} unmatched frame(s).")
        for frame in actual_frames:
            lines.append(frame.describe())
            lines.append("Observed PCS blocks for unmatched frame:")
            lines.append(indent_block(format_recent_records(frame.blocks, empty_message="<empty>")))

    if recent_expected_activity:
        lines.append("Recent expected-side AXI activity:")
        lines.append(
            indent_block(
                format_recent_records(
                    recent_expected_activity,
                    empty_message="<no recent expected activity>",
                )
            )
        )

    if recent_actual_blocks:
        lines.append("Recent observed PCS blocks:")
        lines.append(
            indent_block(
                format_recent_records(
                    recent_actual_blocks,
                    empty_message="<no recent observed blocks>",
                )
            )
        )

    return "\n".join(lines)
