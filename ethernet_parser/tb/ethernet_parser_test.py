import random
import cocotb

from ethernet_parser.tb.ethernet_parser_test_base import EthernetParserTestBase
from tb_utils.tb_common import initialize_tb


PRE_FRAME_IDLES = 4


def _make_frame(fill_byte: int = 0x00) -> list[int]:
    return [fill_byte] * 64


def _make_other_frame(fill_byte: int = 0x5A) -> list[int]:
    frame = _make_frame(fill_byte)
    frame[12] = 0x34
    frame[13] = 0x12
    return frame


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
