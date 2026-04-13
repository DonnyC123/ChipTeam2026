import random

import cocotb
from cocotb.triggers import Event, RisingEdge

from tb_utils.tb_common import initialize_tb
from tx_pcs_generator_test_base import TxPcsGeneratorTestBase


SYNC_DATA = 0b01
SYNC_CONTROL = 0b10
BLOCK_IDLE = 0x1E
TERM_TYPES = {0x87, 0x99, 0xAA, 0xB4, 0xCC, 0xD2, 0xE1, 0xFF}


def _bytes_to_word_little_endian(byte_values):
    word = 0
    for lane, b in enumerate(byte_values):
        word |= (int(b) & 0xFF) << (8 * lane)
    return word


def _packet_to_axis_words(packet_bytes):
    words = []
    idx = 0
    while idx < len(packet_bytes):
        chunk = packet_bytes[idx : idx + 8]
        keep = (1 << len(chunk)) - 1
        data = _bytes_to_word_little_endian(chunk)
        last = 1 if (idx + 8) >= len(packet_bytes) else 0
        words.append((data, keep, last))
        idx += 8
    return words


async def _push_axis_word(
    testbase: TxPcsGeneratorTestBase,
    data: int,
    keep: int,
    last: int,
    out_ready_fn,
):
    accepted = False
    while not accepted:
        ready_now = int(testbase.dut.in_ready_o.value)
        await testbase.sequence.add_cycle(
            valid=True,
            data=data,
            keep=keep,
            last=last,
            out_ready=1,
        )
        await RisingEdge(testbase.dut.clk)
        accepted = bool(ready_now)

    # Leave one clean idle beat between words so a new word does not
    # accidentally overwrite a held transaction in the generic driver.
    await testbase.sequence.add_cycle(
        valid=False,
        out_ready=out_ready_fn(),
    )
    await RisingEdge(testbase.dut.clk)


async def _wait_ingress_ready(testbase: TxPcsGeneratorTestBase, out_ready_fn):
    while not int(testbase.dut.in_ready_o.value):
        await testbase.sequence.add_cycle(
            valid=False,
            out_ready=out_ready_fn(),
        )
        await RisingEdge(testbase.dut.clk)


async def _push_packet(testbase: TxPcsGeneratorTestBase, payload: bytes, out_ready_fn):
    for data, keep, last in _packet_to_axis_words(payload):
        await _wait_ingress_ready(testbase, out_ready_fn)
        await _push_axis_word(
            testbase=testbase,
            data=data,
            keep=keep,
            last=last,
            out_ready_fn=out_ready_fn,
        )


async def _capture_blocks(dut, sink, stop_event: Event):
    while True:
        await RisingEdge(dut.clk)
        if stop_event.is_set():
            return
        if int(dut.out_valid_o.value) and int(dut.out_ready_i.value):
            sink.append((int(dut.out_data_o.value), int(dut.out_control_o.value)))


async def _flush_actual_queue(testbase: TxPcsGeneratorTestBase):
    while not testbase.monitor.actual_queue.empty():
        await testbase.monitor.actual_queue.get()


@cocotb.test()
async def tx_pcs_generator_idle_stream_test(dut):
    """No input traffic: output must continuously emit idle control blocks."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxPcsGeneratorTestBase(dut)
    await _flush_actual_queue(testbase)

    await testbase.sequence.add_idle(cycles=40, out_ready=1)

    await testbase.driver.wait_until_idle()
    await RisingEdge(dut.clk)
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_pcs_generator_shortest_supported_frame_test(dut):
    """Shortest supported frame (7 bytes): must emit S0 then T0 sequence."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxPcsGeneratorTestBase(dut)
    await _flush_actual_queue(testbase)

    payload = bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77])
    await _push_packet(testbase, payload, out_ready_fn=lambda: 1)
    await testbase.sequence.add_idle(cycles=20, out_ready=1)

    await testbase.driver.wait_until_idle()
    await RisingEdge(dut.clk)
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_pcs_generator_terminate_k_coverage_test(dut):
    """Cover T0..T7 terminate block types by controlling frame tail lengths."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxPcsGeneratorTestBase(dut)
    await _flush_actual_queue(testbase)

    observed_control_types = set()
    captured = []
    stop_event = Event()
    capture_task = cocotb.start_soon(_capture_blocks(dut, captured, stop_event))

    rng = random.Random(0xA211_2026)
    for k in range(8):
        frame_len = 7 + k
        payload = bytes(rng.getrandbits(8) for _ in range(frame_len))
        await _push_packet(testbase, payload, out_ready_fn=lambda: 1)
        await testbase.sequence.add_idle(cycles=6, out_ready=1)

    await testbase.sequence.add_idle(cycles=40, out_ready=1)
    await testbase.driver.wait_until_idle()

    stop_event.set()
    await RisingEdge(dut.clk)
    await capture_task

    for data, control in captured:
        if control == SYNC_CONTROL:
            observed_control_types.add(data & 0xFF)

    assert BLOCK_IDLE in observed_control_types, "Idle control block was never observed"
    assert TERM_TYPES.issubset(observed_control_types), (
        f"Missing terminate block types: {sorted(TERM_TYPES - observed_control_types)}"
    )

    await testbase.scoreboard.check()


@cocotb.test()
async def tx_pcs_generator_back_to_back_frames_test(dut):
    """Back-to-back frames without explicit spacing must remain protocol-correct."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxPcsGeneratorTestBase(dut)
    await _flush_actual_queue(testbase)

    packets = [
        bytes(range(0x10, 0x10 + 13)),
        bytes(range(0x30, 0x30 + 21)),
        bytes(range(0x60, 0x60 + 8)),
        bytes(range(0x80, 0x80 + 25)),
    ]
    for payload in packets:
        await _push_packet(testbase, payload, out_ready_fn=lambda: 1)

    await testbase.sequence.add_idle(cycles=64, out_ready=1)

    await testbase.driver.wait_until_idle()
    await RisingEdge(dut.clk)
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_pcs_generator_in_frame_input_bubble_test(dut):
    """Inject input bubbles mid-frame; encoder must wait and preserve frame state."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxPcsGeneratorTestBase(dut)
    await _flush_actual_queue(testbase)

    payload = bytes(range(0x20, 0x20 + 20))
    words = _packet_to_axis_words(payload)

    first_data, first_keep, first_last = words[0]
    await _push_axis_word(
        testbase=testbase,
        data=first_data,
        keep=first_keep,
        last=first_last,
        out_ready_fn=lambda: 1,
    )

    await testbase.sequence.add_idle(cycles=24, out_ready=1)

    for data, keep, last in words[1:]:
        await _push_axis_word(
            testbase=testbase,
            data=data,
            keep=keep,
            last=last,
            out_ready_fn=lambda: 1,
        )

    await testbase.sequence.add_idle(cycles=40, out_ready=1)

    await testbase.driver.wait_until_idle()
    await RisingEdge(dut.clk)
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_pcs_generator_random_protocol_stress_test(dut):
    """Random frame sizes + random out_ready jitter, with legal AXIS keep/last behavior."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxPcsGeneratorTestBase(dut)
    await _flush_actual_queue(testbase)

    rng = random.Random(0x5043_5326)
    num_packets = 80

    for _ in range(num_packets):
        frame_len = rng.randint(7, 220)
        payload = bytes(rng.getrandbits(8) for _ in range(frame_len))

        await _push_packet(
            testbase,
            payload,
            out_ready_fn=lambda: 1 if rng.random() < 0.78 else 0,
        )

        await testbase.sequence.add_idle(cycles=rng.randint(0, 4), out_ready=1)

    for _ in range(300):
        await testbase.sequence.add_idle(
            cycles=1, out_ready=(1 if rng.random() < 0.82 else 0)
        )

    await testbase.driver.wait_until_idle()
    await RisingEdge(dut.clk)
    await testbase.scoreboard.check()
