import random
import cocotb
from cocotb.triggers import ReadOnly, RisingEdge

from ethernet_parser.tb.ethernet_parser_sequence_item import (
    EthernetParserSequenceItem,
)
from ethernet_parser.tb.ethernet_parser_test_base import EthernetParserTestBase
from tb_utils.tb_common import initialize_tb


PRE_FRAME_IDLES = 4
RANDOM_STRESS_FRAMES = 200


def _make_frame(fill_byte: int = 0x00) -> list[int]:
    return [fill_byte] * 64


def _make_frame_with_length(length: int, fill_byte: int = 0x00) -> list[int]:
    return [fill_byte] * length


def _set_ethertype(frame: list[int], kind: str):
    if kind == "IPV4":
        frame[12:14] = [0x00, 0x08]
    elif kind == "IPV6":
        frame[12:14] = [0xDD, 0x86]
    elif kind == "OTHER":
        frame[12:14] = [0x34, 0x12]
    else:
        raise ValueError("kind must be IPV4, IPV6, or OTHER")


def _make_typed_frame(kind: str, fill_byte: int = 0x00, length: int = 64) -> list[int]:
    frame = _make_frame_with_length(length, fill_byte)
    _set_ethertype(frame, kind)
    return frame


def _make_other_frame(fill_byte: int = 0x5A) -> list[int]:
    return _make_typed_frame("OTHER", fill_byte)


def _make_random_frame(rng: random.Random, length: int) -> list[int]:
    return [rng.randrange(256) for _ in range(length)]


def _needs_explicit_eof(tb, frame: list[int], start_mode: str) -> bool:
    start_config = tb.sequence._resolve_start_mode(start_mode)
    return (len(frame) - start_config["start_count"]) % tb.sequence.DATA_BYTES == 0


async def _send_frame_with_start_mode(
    tb,
    frame: list[int],
    *,
    start_mode: str,
    explicit_eof_mask: int | None = None,
):
    tb.sequence.set_manual_frame(frame)
    start_config = tb.sequence._resolve_start_mode(start_mode)
    expected_output = tb.sequence._expected_output_from_frame()
    parse_result_item_idx = start_config["parse_result_item_idx"]

    await tb.sequence._drive_frame(
        start_count=start_config["start_count"],
        start_lane=start_config["start_lane"],
        start_mask=start_config["start_mask"],
        expected_outputs_overrides={
            parse_result_item_idx: expected_output,
        },
        expected_payload_time_overrides={
            parse_result_item_idx: True,
        },
    )

    if explicit_eof_mask is not None and _needs_explicit_eof(
        tb, frame, start_mode
    ):
        await tb.sequence._drive_word(
            0,
            explicit_eof_mask,
            EthernetParserSequenceItem.OUTPUT_OTHER,
            valid=True,
        )


async def _wait_for_driven_word(dut, *, bytes_valid: int):
    while True:
        await RisingEdge(dut.clk)
        await ReadOnly()
        if int(dut.data_valid_i.value) and int(dut.bytes_valid_i.value) == bytes_valid:
            return


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def _wait_for_valid_output_with_previous_payload(dut, *, expected_output: int):
    previous_payload_time = 0
    while True:
        await RisingEdge(dut.clk)
        await ReadOnly()

        current_payload_time = _to_int(dut.payload_time_o.value, 0)
        if _to_int(dut.valid_o.value, 0):
            observed_output = _to_int(dut.outputs_o.value)
            assert observed_output == expected_output, (
                f"expected outputs_o={expected_output}, got {observed_output}"
            )
            assert previous_payload_time == 1, (
                "expected payload_time_o=1 on the cycle before "
                f"outputs_o={expected_output}"
            )
            return

        previous_payload_time = current_payload_time


@cocotb.test()
async def test_single_ipv4_frame(dut):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)

    frame = _make_frame(0x11)

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    await tb.sequence.send_IPV4_ethernet(frame)
    await tb.sequence.send_idles(4)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_single_ipv6_frame(dut):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)

    frame = _make_frame(0x22)

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    await tb.sequence.send_IPV6_ethernet(frame)
    await tb.sequence.send_idles(4)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_payload_time_precedes_ipv_outputs_raw_timing(dut):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)

    cases = [
        ("IPV4", "sof0", EthernetParserSequenceItem.OUTPUT_IPV4, 0xA1),
        ("IPV6", "sof0", EthernetParserSequenceItem.OUTPUT_IPV6, 0xA2),
        ("IPV4", "sof4", EthernetParserSequenceItem.OUTPUT_IPV4, 0xA3),
        ("IPV6", "sof4", EthernetParserSequenceItem.OUTPUT_IPV6, 0xA4),
    ]

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    for kind, start_mode, expected_output, fill_byte in cases:
        frame = _make_typed_frame(kind, fill_byte)
        await _send_frame_with_start_mode(tb, frame, start_mode=start_mode)
        await _wait_for_valid_output_with_previous_payload(
            dut,
            expected_output=expected_output,
        )
        await tb.sequence.send_idles(2)

    await tb.sequence.send_idles(4)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_single_ipv4_frame_sof4(dut):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)

    frame = _make_frame(0x33)

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    await tb.sequence.send_IPV4_ethernet(frame, start_mode="sof4")
    await tb.sequence.send_idles(4)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_single_ipv6_frame_sof4(dut):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)

    frame = _make_frame(0x24)

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    await tb.sequence.send_IPV6_ethernet(frame, start_mode="sof4")
    await tb.sequence.send_idles(4)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_single_other_frame(dut):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)

    frame = _make_other_frame()

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    await tb.sequence.send_ethernet_frame(frame)
    await tb.sequence.send_idles(4)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_single_other_frame_sof4(dut):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)

    frame = _make_other_frame(0x5B)

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    await _send_frame_with_start_mode(tb, frame, start_mode="sof4")
    await tb.sequence.send_idles(4)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_sof0_first_word_sets_sof_type_high(dut):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)

    frame = _make_other_frame(0x77)

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    tb.sequence.set_manual_frame(frame)
    await tb.sequence.sof0_driver()
    await _wait_for_driven_word(dut, bytes_valid=tb.sequence.SOF0_MASK)

    await RisingEdge(dut.clk)
    await ReadOnly()
    assert (
        str(dut.sof_type_o.value) == "1"
    ), f"expected sof_type_o=1 after sof0 first word, got {dut.sof_type_o.value!s}"

    await tb.sequence.send_idles(4)
    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_sof4_first_word_sets_sof_type_low(dut):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)

    frame = _make_other_frame(0x88)

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    tb.sequence.set_manual_frame(frame)
    await tb.sequence.sof4_driver()
    await _wait_for_driven_word(dut, bytes_valid=tb.sequence.SOF4_MASK)

    await RisingEdge(dut.clk)
    await ReadOnly()
    assert (
        str(dut.sof_type_o.value) == "0"
    ), f"expected sof_type_o=0 after sof4 first word, got {dut.sof_type_o.value!s}"

    await tb.sequence.send_idles(4)
    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_zero_gap_back_to_back_all_frame_types_and_starts(dut):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)

    frames = [
        (_make_typed_frame("IPV4", 0x10), "sof0"),
        (_make_typed_frame("IPV6", 0x20), "sof4"),
        (_make_typed_frame("OTHER", 0x30), "sof0"),
        (_make_typed_frame("IPV4", 0x40), "sof4"),
        (_make_typed_frame("IPV6", 0x50), "sof0"),
        (_make_typed_frame("OTHER", 0x60), "sof4"),
    ]

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    for frame, start_mode in frames:
        await _send_frame_with_start_mode(tb, frame, start_mode=start_mode)
    await tb.sequence.send_idles(4)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_full_word_aligned_frame_uses_e0_as_eof_not_sof4(dut):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)

    aligned_frame = _make_typed_frame("IPV4", 0x71, length=71)
    followup_frame = _make_typed_frame("IPV6", 0x72)

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    await _send_frame_with_start_mode(
        tb,
        aligned_frame,
        start_mode="sof0",
        explicit_eof_mask=tb.sequence.SOF4_MASK,
    )
    await _send_frame_with_start_mode(tb, followup_frame, start_mode="sof4")
    await tb.sequence.send_idles(4)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_full_word_aligned_frame_uses_fe_as_eof_not_sof0(dut):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)

    aligned_frame = _make_typed_frame("IPV6", 0x81, length=67)
    followup_frame = _make_typed_frame("IPV4", 0x82)

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    await _send_frame_with_start_mode(
        tb,
        aligned_frame,
        start_mode="sof4",
        explicit_eof_mask=tb.sequence.SOF0_MASK,
    )
    await _send_frame_with_start_mode(tb, followup_frame, start_mode="sof0")
    await tb.sequence.send_idles(4)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_back_to_back_mixed_frames(dut):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)

    ipv4_frame = _make_frame(0x33)
    ipv6_frame = _make_frame(0x44)
    other_frame = _make_other_frame(0x55)

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    await tb.sequence.send_IPV4_ethernet(ipv4_frame)
    await tb.sequence.send_idles(2)
    await tb.sequence.send_IPV6_ethernet(ipv6_frame)
    await tb.sequence.send_idles(2)
    await tb.sequence.send_ethernet_frame(other_frame)
    await tb.sequence.send_idles(4)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_variable_lengths_and_tail_masks(dut):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)

    cases = [
        (_make_typed_frame("IPV4", 0x91, length=64), "sof0"),
        (_make_typed_frame("IPV6", 0x92, length=65), "sof0"),
        (_make_typed_frame("OTHER", 0x93, length=70), "sof0"),
        (_make_typed_frame("IPV4", 0x94, length=64), "sof4"),
        (_make_typed_frame("IPV6", 0x95, length=65), "sof4"),
        (_make_typed_frame("OTHER", 0x96, length=70), "sof4"),
    ]

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    for frame, start_mode in cases:
        await _send_frame_with_start_mode(tb, frame, start_mode=start_mode)
        await tb.sequence.send_idles(1)
    await tb.sequence.send_idles(4)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_invalid_gaps_do_not_enqueue_outputs(dut, seed: int = 0xDEADBEEF):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)
    rng = random.Random(seed)

    frame = _make_other_frame(0x66)

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    await tb.sequence.send_invalid_blocks(5)
    await tb.sequence.send_idles(rng.randint(1, 4))
    await tb.sequence.send_ethernet_frame(frame)
    await tb.sequence.send_invalid_blocks(3)
    await tb.sequence.send_idles(4)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_random_constrained_frames(dut, seed: int = 0xC0FFEE):
    await initialize_tb(dut)
    tb = EthernetParserTestBase(dut)
    rng = random.Random(seed)

    await tb.sequence.send_idles(PRE_FRAME_IDLES)
    for _ in range(RANDOM_STRESS_FRAMES):
        frame_kind = rng.choice(("RANDOM", "IPV4", "IPV6"))
        start_mode = rng.choice(("sof0", "sof4"))
        frame = _make_random_frame(rng, rng.randint(64, 151))

        if frame_kind in ("IPV4", "IPV6"):
            _set_ethertype(frame, frame_kind)

        explicit_eof_mask = rng.choice(
            (tb.sequence.SOF0_MASK, tb.sequence.SOF4_MASK)
        )
        await _send_frame_with_start_mode(
            tb,
            frame,
            start_mode=start_mode,
            explicit_eof_mask=explicit_eof_mask,
        )
        await tb.sequence.send_idles(rng.randint(0, 3))

    await tb.sequence.send_idles(8)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()
