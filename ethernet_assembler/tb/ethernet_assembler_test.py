import os
import random

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge

from ethernet_assembler.tb.ethernet_assembler_test_base import EthernetAssemblerTestBase
from tb_utils.tb_common import initialize_tb


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)), 0)


def _env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _sample_outputs(dut) -> dict[str, int]:
    return {
        "drop_frame": int(dut.drop_frame_o.value),
        "out_valid": int(dut.out_valid_o.value),
        "bytes_valid": int(dut.bytes_valid_o.value),
    }


async def _drain_driver_and_capture(testbase: EthernetAssemblerTestBase, settle_cycles: int = 2):
    samples = []

    while await testbase.driver.busy():
        await RisingEdge(testbase.dut.clk)
        await ReadOnly()
        samples.append(_sample_outputs(testbase.dut))

    for _ in range(settle_cycles):
        await RisingEdge(testbase.dut.clk)
        await ReadOnly()
        samples.append(_sample_outputs(testbase.dut))

    return samples


async def _finalize_and_check(testbase: EthernetAssemblerTestBase):
    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


def _pick_unknown_control_block_type(seq, rng: random.Random) -> int:
    valid_control_set = {
        seq.IDLE_BLK,
        seq.SOF_L0,
        seq.SOF_L4,
        seq.TERM_L0,
        seq.TERM_L1,
        seq.TERM_L2,
        seq.TERM_L3,
        seq.TERM_L4,
        seq.TERM_L5,
        seq.TERM_L6,
        seq.TERM_L7,
        seq.OS_D6,
        seq.OS_D5,
        seq.OS_D3T,
        seq.OS_D3B,
    }
    block_type = rng.getrandbits(seq.BLOCK_TYPE_W)
    while block_type in valid_control_set:
        block_type = rng.getrandbits(seq.BLOCK_TYPE_W)
    return block_type


_TERM_IPG_BYTES = {
    0x87: 7,
    0x99: 6,
    0xAA: 5,
    0xB4: 4,
    0xCC: 3,
    0xD2: 2,
    0xE1: 1,
    0xFF: 0,
}

_START_IPG_MIN = {
    0x78: 12,
    0x33: 8,
}

_START_BYTES_VALID = {
    0x78: 0b1111_1110,
    0x33: 0b1110_0000,
}


def _restart_ipg_is_legal(term_block_type: int, idle_count: int, start_block_type: int) -> bool:
    return (_TERM_IPG_BYTES[term_block_type] + (8 * idle_count)) >= _START_IPG_MIN[start_block_type]


async def _enqueue_random_sequence_action(
    seq,
    rng: random.Random,
    *,
    include_cancel_helper: bool,
    max_cancel_len: int,
) -> str:
    in_valid = rng.random() < 0.90
    locked = rng.random() < 0.92

    start_helpers = (seq.add_sof_l0, seq.add_sof_l4)
    term_helpers = (
        seq.add_term_l0,
        seq.add_term_l1,
        seq.add_term_l2,
        seq.add_term_l3,
        seq.add_term_l4,
        seq.add_term_l5,
        seq.add_term_l6,
        seq.add_term_l7,
    )
    ordered_set_helpers = (seq.add_os_d6, seq.add_os_d5, seq.add_os_d3t, seq.add_os_d3b)

    action_pool = [
        "add_idle_blk",
        "add_manual_idle_chunk",
        "add_random_idle_chunk",
        "add_random_data",
        "add_bad_header",
        "add_random_start",
        "add_random_end",
        "add_manual_data",
        "add_manual_start",
        "add_manual_end",
        "add_data_header",
        "add_control_header_known",
        "add_control_header_unknown",
        "add_start_helper",
        "add_term_helper",
        "add_ordered_set_helper",
    ]

    if include_cancel_helper:
        action_pool.append("start_and_cancel_frame")

    action = rng.choice(action_pool)
    payload = rng.getrandbits(seq.PAYLOAD_W)
    payload_low = rng.getrandbits(seq.CONTROL_DATA_W)

    if action == "add_idle_blk":
        await seq.add_idle_blk(
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
        )
    elif action == "add_manual_idle_chunk":
        await seq.add_manual_idle_chunk(
            count=rng.randint(0, 4),
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
        )
    elif action == "add_random_idle_chunk":
        await seq.add_random_idle_chunk(
            min_count=0,
            max_count=4,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
            rng=rng,
        )
    elif action == "add_random_data":
        await seq.add_random_data(
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
            rng=rng,
        )
    elif action == "add_bad_header":
        await seq.add_bad_header(
            payload=payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
            rng=rng,
        )
    elif action == "add_random_start":
        await seq.add_random_start(
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
            rng=rng,
        )
    elif action == "add_random_end":
        await seq.add_random_end(
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
            rng=rng,
        )
    elif action == "add_manual_data":
        await seq.add_manual_data(
            payload=payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
        )
    elif action == "add_manual_start":
        await seq.add_manual_start(
            payload=payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
            rng=rng,
        )
    elif action == "add_manual_end":
        await seq.add_manual_end(
            payload=payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
            rng=rng,
        )
    elif action == "add_data_header":
        await seq.add_data_header(
            payload=payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
        )
    elif action == "add_control_header_known":
        known_control_blocks = (
            seq.IDLE_BLK,
            seq.SOF_L0,
            seq.SOF_L4,
            seq.TERM_L0,
            seq.TERM_L1,
            seq.TERM_L2,
            seq.TERM_L3,
            seq.TERM_L4,
            seq.TERM_L5,
            seq.TERM_L6,
            seq.TERM_L7,
            seq.OS_D6,
            seq.OS_D5,
            seq.OS_D3T,
            seq.OS_D3B,
        )
        block_type = rng.choice(known_control_blocks)
        control_payload = seq._compose_control_payload(
            block_type=block_type,
            payload_low=payload_low,
        )
        await seq.add_control_header(
            payload=control_payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
        )
    elif action == "add_control_header_unknown":
        block_type = _pick_unknown_control_block_type(seq, rng)
        control_payload = seq._compose_control_payload(
            block_type=block_type,
            payload_low=payload_low,
        )
        await seq.add_control_header(
            payload=control_payload,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
        )
    elif action == "add_start_helper":
        await rng.choice(start_helpers)(
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
        )
    elif action == "add_term_helper":
        await rng.choice(term_helpers)(
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
        )
    elif action == "add_ordered_set_helper":
        await rng.choice(ordered_set_helpers)(
            payload_low=payload_low,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=False,
        )
    else:
        cancel_len = rng.randint(0, max_cancel_len)
        await seq.start_and_cancel_frame(
            len=cancel_len,
            in_valid=True,
            locked=True,
            rng=rng,
        )

    return action


# Section A: Directed frame sanity.
@cocotb.test()
async def batch_valid_frame_start_to_end_test(dut):
    await initialize_tb(dut, clk_period_ns=_env_int("EA_CLK_PERIOD_NS", 10))
    testbase = EthernetAssemblerTestBase(dut)
    seq = testbase.sequence

    seed = _env_int("EA_BATCH_VALID_SEED", 0x1A2B3C4D)
    frame_count = _env_int("EA_BATCH_VALID_FRAMES", 8)
    max_extra_data = _env_int("EA_BATCH_VALID_MAX_EXTRA_DATA", 4)
    rng = random.Random(seed)

    cocotb.log.info(
        "batch_valid_frame_start_to_end_test seed=0x%08X frames=%d",
        seed,
        frame_count,
    )

    for frame_idx in range(frame_count):
        await seq.add_random_start(rng=rng)
        for _ in range(rng.randint(0, max_extra_data)):
            await seq.add_random_data(rng=rng)
        await seq.add_random_end(rng=rng)
        if frame_idx != (frame_count - 1):
            await seq.add_random_idle_chunk(
                min_count=2,
                max_count=4,
                rng=rng,
            )

    await _finalize_and_check(testbase)


# Section B: Directed helper matrix.
@cocotb.test()
async def batch_helper_function_matrix_test(dut):
    await initialize_tb(dut, clk_period_ns=_env_int("EA_CLK_PERIOD_NS", 10))
    testbase = EthernetAssemblerTestBase(dut)
    seq = testbase.sequence

    seed = _env_int("EA_BATCH_HELPER_SEED", 0x55667788)
    rounds = _env_int("EA_BATCH_HELPER_ROUNDS", 6)
    max_os_data_pairs = _env_int("EA_BATCH_HELPER_MAX_OS_PAIRS", 3)
    rng = random.Random(seed)

    start_helpers = (seq.add_sof_l0, seq.add_sof_l4)
    ordered_set_helpers = (seq.add_os_d6, seq.add_os_d5, seq.add_os_d3t, seq.add_os_d3b)
    term_helpers = (
        seq.add_term_l0,
        seq.add_term_l1,
        seq.add_term_l2,
        seq.add_term_l3,
        seq.add_term_l4,
        seq.add_term_l5,
        seq.add_term_l6,
        seq.add_term_l7,
    )

    cocotb.log.info(
        "batch_helper_function_matrix_test seed=0x%08X rounds=%d",
        seed,
        rounds,
    )

    for _ in range(rounds):
        await seq.add_idle_blk()
        await seq.add_random_data(rng=rng)
        await seq.add_random_idle_chunk(
            min_count=2,
            max_count=4,
            rng=rng,
        )
        await rng.choice(start_helpers)()
        for _ in range(rng.randint(1, max_os_data_pairs)):
            await rng.choice(ordered_set_helpers)()
            await seq.add_random_data(rng=rng)
        await rng.choice(term_helpers)()

    await _finalize_and_check(testbase)


# Section C: Directed cancel/recovery contract observations.
@cocotb.test()
async def batch_cancel_recovery_contract_test(dut):
    await initialize_tb(dut, clk_period_ns=_env_int("EA_CLK_PERIOD_NS", 10))
    testbase = EthernetAssemblerTestBase(dut)
    seq = testbase.sequence

    seed = _env_int("EA_BATCH_CANCEL_SEED", 0xC0FFEE11)
    cancel_len = max(1, _env_int("EA_BATCH_CANCEL_LEN", 3))
    post_cancel_data = _env_int("EA_BATCH_CANCEL_POST_DATA", 5)
    rng = random.Random(seed)

    cocotb.log.info(
        "batch_cancel_recovery_contract_test seed=0x%08X cancel_len=%d",
        seed,
        cancel_len,
    )

    await seq.start_and_cancel_frame(len=cancel_len, rng=rng)
    cancel_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["drop_frame"] == 1 for sample in cancel_phase), (
        "Expected drop_frame_o to pulse when canceling an active frame"
    )

    for _ in range(post_cancel_data):
        await seq.add_random_data(rng=rng)
    await seq.add_idle_blk()
    await seq.add_term_l7()
    suppressed_phase = await _drain_driver_and_capture(testbase)
    assert all(sample["out_valid"] == 0 for sample in suppressed_phase), (
        "Expected out_valid_o to stay low after cancel until a new start frame arrives"
    )

    await seq.add_random_idle_chunk(
        min_count=2,
        max_count=4,
        rng=rng,
    )
    await seq.add_random_start(rng=rng)
    recover_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["out_valid"] == 1 for sample in recover_phase), (
        "Expected out_valid_o to recover after a new start frame"
    )

    await seq.start_and_cancel_frame(len=0, rng=rng)
    cancel_phase_len0 = await _drain_driver_and_capture(testbase)
    assert any(sample["drop_frame"] == 1 for sample in cancel_phase_len0), (
        "Expected drop_frame_o to pulse for len=0 cancel when already in-frame"
    )

    for _ in range(max(2, post_cancel_data // 2)):
        await seq.add_random_data(rng=rng)
    suppressed_phase_len0 = await _drain_driver_and_capture(testbase)
    assert all(sample["out_valid"] == 0 for sample in suppressed_phase_len0), (
        "Expected out_valid_o to remain low after len=0 cancel until start"
    )

    await seq.add_random_idle_chunk(
        min_count=2,
        max_count=4,
        rng=rng,
    )
    await seq.add_random_start(rng=rng)
    recover_phase_len0 = await _drain_driver_and_capture(testbase)
    assert any(sample["out_valid"] == 1 for sample in recover_phase_len0), (
        "Expected out_valid_o to recover after start following len=0 cancel"
    )
    await seq.add_random_end(rng=rng)

    # This test does direct waveform-style observation checks while the sequence runs.
    # Do not run scoreboard compare here, because the direct observation helper
    # intentionally allows gap cycles that are not mirrored into model notifications.
    await testbase.wait_for_driver_done()


# Section D: Random helper combinations from sequence API.
@cocotb.test()
async def random_sequence_function_combinations_test(dut):
    await initialize_tb(dut, clk_period_ns=_env_int("EA_CLK_PERIOD_NS", 10))
    testbase = EthernetAssemblerTestBase(dut)
    seq = testbase.sequence

    seed = _env_int("EA_RANDOM_HELPER_SEED", 0x9BADC0DE)
    steps = _env_int("EA_RANDOM_HELPER_STEPS", 180)
    include_cancel_helper = _env_flag("EA_RANDOM_HELPER_INCLUDE_CANCEL", default=False)
    max_cancel_len = max(0, _env_int("EA_RANDOM_HELPER_MAX_CANCEL_LEN", 4))
    rng = random.Random(seed)

    cocotb.log.info(
        "random_sequence_function_combinations_test seed=0x%08X steps=%d include_cancel=%d",
        seed,
        steps,
        int(include_cancel_helper),
    )

    for step in range(steps):
        action_name = await _enqueue_random_sequence_action(
            seq,
            rng,
            include_cancel_helper=include_cancel_helper,
            max_cancel_len=max_cancel_len,
        )
        if step < 20 or (step % 50 == 0):
            cocotb.log.info("random-step=%03d action=%s", step, action_name)

    await _finalize_and_check(testbase)


# Section E: Directed edge cases.
@cocotb.test()
async def edge_case_bad_header_invalid_does_not_drop_test(dut):
    await initialize_tb(dut, clk_period_ns=_env_int("EA_CLK_PERIOD_NS", 10))
    testbase = EthernetAssemblerTestBase(dut)
    seq = testbase.sequence
    rng = random.Random(_env_int("EA_EDGE_INVALID_BAD_HDR_SEED", 0xA11CE001))

    await seq.add_random_start(rng=rng)
    start_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["out_valid"] == 1 for sample in start_phase), (
        "Expected a valid output when entering frame with start helper"
    )

    await seq.add_bad_header(
        payload=rng.getrandbits(seq.PAYLOAD_W),
        in_valid=False,
        locked=True,
        cancel_frame=False,
        rng=rng,
    )
    invalid_bad_hdr_phase = await _drain_driver_and_capture(testbase)
    assert all(sample["drop_frame"] == 0 for sample in invalid_bad_hdr_phase), (
        "Expected no drop_frame_o pulse for bad header when in_valid_i=0"
    )

    await seq.add_random_data(rng=rng)
    post_invalid_bad_hdr_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["out_valid"] == 1 for sample in post_invalid_bad_hdr_phase), (
        "Expected frame to remain active after invalid bad-header cycle"
    )

    await seq.add_random_end(rng=rng)
    await _finalize_and_check(testbase)


@cocotb.test()
async def edge_case_bad_header_valid_drops_frame_test(dut):
    await initialize_tb(dut, clk_period_ns=_env_int("EA_CLK_PERIOD_NS", 10))
    testbase = EthernetAssemblerTestBase(dut)
    seq = testbase.sequence
    rng = random.Random(_env_int("EA_EDGE_VALID_BAD_HDR_SEED", 0xA11CE002))

    await seq.add_random_start(rng=rng)
    _ = await _drain_driver_and_capture(testbase)

    await seq.add_bad_header(
        payload=rng.getrandbits(seq.PAYLOAD_W),
        in_valid=True,
        locked=True,
        cancel_frame=False,
        rng=rng,
    )
    valid_bad_hdr_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["drop_frame"] == 1 for sample in valid_bad_hdr_phase), (
        "Expected drop_frame_o pulse for bad header when in_valid_i=1"
    )

    await seq.add_random_data(rng=rng)
    suppressed_phase = await _drain_driver_and_capture(testbase)
    assert all(sample["out_valid"] == 0 for sample in suppressed_phase), (
        "Expected out_valid_o low after frame drop until a new start frame"
    )

    await seq.add_manual_idle_chunk(count=0)
    await seq.add_sof_l4(in_valid=True, locked=True, cancel_frame=False)
    blocked_recovery_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["drop_frame"] == 1 for sample in blocked_recovery_phase), (
        "Expected immediate restart after bad-header drop to violate minimum IPG"
    )

    await seq.add_manual_idle_chunk(count=1)
    await seq.add_sof_l4(in_valid=True, locked=True, cancel_frame=False)
    recovery_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["bytes_valid"] == 0b1110_0000 for sample in recovery_phase), (
        "Expected out_valid_o recovery after fresh start frame with legal IPG"
    )

    await seq.add_random_end(rng=rng)
    await _finalize_and_check(testbase)


@cocotb.test()
async def edge_case_lock_loss_requires_in_valid_test(dut):
    await initialize_tb(dut, clk_period_ns=_env_int("EA_CLK_PERIOD_NS", 10))
    testbase = EthernetAssemblerTestBase(dut)
    seq = testbase.sequence
    rng = random.Random(_env_int("EA_EDGE_LOCK_LOSS_SEED", 0xA11CE003))

    await seq.add_random_start(rng=rng)
    _ = await _drain_driver_and_capture(testbase)

    await seq.add_random_data(
        in_valid=False,
        locked=False,
        cancel_frame=False,
        rng=rng,
    )
    invalid_lock_loss_phase = await _drain_driver_and_capture(testbase)
    assert all(sample["drop_frame"] == 0 for sample in invalid_lock_loss_phase), (
        "Expected no drop_frame_o when locked_i=0 but in_valid_i=0"
    )

    await seq.add_random_data(
        in_valid=True,
        locked=False,
        cancel_frame=False,
        rng=rng,
    )
    valid_lock_loss_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["drop_frame"] == 1 for sample in valid_lock_loss_phase), (
        "Expected drop_frame_o pulse when locked_i=0 and in_valid_i=1 in-frame"
    )

    await seq.add_random_data(rng=rng)
    post_drop_phase = await _drain_driver_and_capture(testbase)
    assert all(sample["out_valid"] == 0 for sample in post_drop_phase), (
        "Expected out_valid_o low after lock-loss drop until new start frame"
    )

    await seq.add_manual_idle_chunk(count=0)
    await seq.add_sof_l4(in_valid=True, locked=True, cancel_frame=False)
    blocked_recovery_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["drop_frame"] == 1 for sample in blocked_recovery_phase), (
        "Expected immediate restart after lock-loss drop to violate minimum IPG"
    )

    await seq.add_manual_idle_chunk(count=1)
    await seq.add_sof_l4(in_valid=True, locked=True, cancel_frame=False)
    recovery_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["bytes_valid"] == 0b1110_0000 for sample in recovery_phase), (
        "Expected output recovery after valid start frame with legal IPG"
    )

    await seq.add_random_end(rng=rng)
    await _finalize_and_check(testbase)


@cocotb.test()
async def edge_case_cancel_in_frame_ignores_in_valid_test(dut):
    await initialize_tb(dut, clk_period_ns=_env_int("EA_CLK_PERIOD_NS", 10))
    testbase = EthernetAssemblerTestBase(dut)
    seq = testbase.sequence
    rng = random.Random(_env_int("EA_EDGE_CANCEL_QUALIFIERS_SEED", 0xA11CE004))

    await seq.add_random_start(rng=rng)
    _ = await _drain_driver_and_capture(testbase)

    await seq.add_random_data(
        in_valid=False,
        locked=True,
        cancel_frame=True,
        rng=rng,
    )
    cancel_low_valid_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["drop_frame"] == 1 for sample in cancel_low_valid_phase), (
        "Expected cancel_frame_i to drop frame even when in_valid_i=0 while in-frame"
    )

    await seq.add_random_data(rng=rng)
    await seq.add_term_l7()
    suppressed_phase = await _drain_driver_and_capture(testbase)
    assert all(sample["out_valid"] == 0 for sample in suppressed_phase), (
        "Expected drop mode suppression after cancel-driven frame abort"
    )

    await seq.add_sof_l0(in_valid=False, locked=True, cancel_frame=False)
    blocked_recovery_phase = await _drain_driver_and_capture(testbase)
    assert all(sample["out_valid"] == 0 for sample in blocked_recovery_phase), (
        "Expected no recovery when SOF is not qualified (in_valid_i=0)"
    )

    await seq.add_manual_idle_chunk(count=0)
    await seq.add_sof_l4(in_valid=True, locked=True, cancel_frame=False)
    ipg_blocked_recovery_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["drop_frame"] == 1 for sample in ipg_blocked_recovery_phase), (
        "Expected immediate restart after cancel drop to violate minimum IPG"
    )

    await seq.add_manual_idle_chunk(count=1)
    await seq.add_sof_l4(in_valid=True, locked=True, cancel_frame=False)
    recovered_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["bytes_valid"] == 0b1110_0000 for sample in recovered_phase), (
        "Expected recovery on first qualified SOF after cancel drop and legal IPG"
    )

    await seq.add_random_end(rng=rng)
    await _finalize_and_check(testbase)


# Manual IPG edge cases.
@cocotb.test()
async def edge_case_ipg_term_l7_idle_sof_l4_accepts_test(dut):
    await initialize_tb(dut, clk_period_ns=_env_int("EA_CLK_PERIOD_NS", 10))
    testbase = EthernetAssemblerTestBase(dut)
    seq = testbase.sequence

    await seq.add_sof_l0()
    _ = await _drain_driver_and_capture(testbase)

    await seq.add_term_l7()
    await seq.add_manual_idle_chunk(count=1)
    await seq.add_sof_l4()
    accept_phase = await _drain_driver_and_capture(testbase)
    assert all(sample["drop_frame"] == 0 for sample in accept_phase), (
        "Expected TERM_L7 + IDLE_BLK + SOF_L4 to satisfy the 12-byte IPG"
    )
    assert any(sample["bytes_valid"] == 0b1110_0000 for sample in accept_phase), (
        "Expected SOF_L4 bytes to be emitted after a legal minimum IPG"
    )

    await seq.add_term_l7()
    await _finalize_and_check(testbase)


@cocotb.test()
async def edge_case_ipg_term_l7_idle_sof_l0_drops_test(dut):
    await initialize_tb(dut, clk_period_ns=_env_int("EA_CLK_PERIOD_NS", 10))
    testbase = EthernetAssemblerTestBase(dut)
    seq = testbase.sequence

    await seq.add_sof_l0()
    _ = await _drain_driver_and_capture(testbase)

    await seq.add_term_l7()
    await seq.add_manual_idle_chunk(count=1)
    await seq.add_sof_l0()
    violation_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["drop_frame"] == 1 for sample in violation_phase), (
        "Expected TERM_L7 + IDLE_BLK + SOF_L0 to violate the 12-byte IPG"
    )
    assert all(sample["bytes_valid"] != 0b1111_1110 for sample in violation_phase), (
        "Expected the violating SOF_L0 block to be suppressed"
    )

    await seq.add_manual_idle_chunk(count=2)
    await seq.add_sof_l0()
    recovery_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["bytes_valid"] == 0b1111_1110 for sample in recovery_phase), (
        "Expected SOF_L0 recovery after restoring the full minimum IPG"
    )

    await seq.add_term_l7()
    await _finalize_and_check(testbase)


@cocotb.test()
async def edge_case_ipg_term_l0_sof_l4_drops_test(dut):
    await initialize_tb(dut, clk_period_ns=_env_int("EA_CLK_PERIOD_NS", 10))
    testbase = EthernetAssemblerTestBase(dut)
    seq = testbase.sequence

    await seq.add_sof_l0()
    _ = await _drain_driver_and_capture(testbase)

    await seq.add_term_l0()
    await seq.add_manual_idle_chunk(count=0)
    await seq.add_sof_l4()
    violation_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["drop_frame"] == 1 for sample in violation_phase), (
        "Expected TERM_L0 + SOF_L4 to violate the 12-byte IPG"
    )
    assert all(sample["bytes_valid"] != 0b1110_0000 for sample in violation_phase), (
        "Expected the violating SOF_L4 block to be suppressed"
    )

    await seq.add_manual_idle_chunk(count=1)
    await seq.add_sof_l4()
    recovery_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["bytes_valid"] == 0b1110_0000 for sample in recovery_phase), (
        "Expected SOF_L4 recovery after restoring the full minimum IPG"
    )

    await seq.add_term_l7()
    await _finalize_and_check(testbase)


@cocotb.test()
async def edge_case_ipg_term_l0_idle_sof_l4_accepts_test(dut):
    await initialize_tb(dut, clk_period_ns=_env_int("EA_CLK_PERIOD_NS", 10))
    testbase = EthernetAssemblerTestBase(dut)
    seq = testbase.sequence

    await seq.add_sof_l0()
    _ = await _drain_driver_and_capture(testbase)

    await seq.add_term_l0()
    await seq.add_manual_idle_chunk(count=1)
    await seq.add_sof_l4()
    accept_phase = await _drain_driver_and_capture(testbase)
    assert all(sample["drop_frame"] == 0 for sample in accept_phase), (
        "Expected TERM_L0 + IDLE_BLK + SOF_L4 to satisfy the 12-byte IPG"
    )
    assert any(sample["bytes_valid"] == 0b1110_0000 for sample in accept_phase), (
        "Expected SOF_L4 bytes to be emitted after a legal minimum IPG"
    )

    await seq.add_term_l7()
    await _finalize_and_check(testbase)


# Section F: Constrained-random IPG restart coverage.
@cocotb.test()
async def constrained_random_ipg_restart_test(dut):
    await initialize_tb(dut, clk_period_ns=_env_int("EA_CLK_PERIOD_NS", 10))
    testbase = EthernetAssemblerTestBase(dut)
    seq = testbase.sequence

    seed = _env_int("EA_RANDOM_IPG_SEED", 0x1F6A2B3C)
    trials = _env_int("EA_RANDOM_IPG_TRIALS", 48)
    max_idle_blocks = max(0, _env_int("EA_RANDOM_IPG_MAX_IDLE_BLOCKS", 3))
    rng = random.Random(seed)

    start_helpers = (
        (seq.SOF_L0, seq.add_sof_l0),
        (seq.SOF_L4, seq.add_sof_l4),
    )
    term_helpers = (
        (seq.TERM_L0, seq.add_term_l0),
        (seq.TERM_L1, seq.add_term_l1),
        (seq.TERM_L2, seq.add_term_l2),
        (seq.TERM_L3, seq.add_term_l3),
        (seq.TERM_L4, seq.add_term_l4),
        (seq.TERM_L5, seq.add_term_l5),
        (seq.TERM_L6, seq.add_term_l6),
        (seq.TERM_L7, seq.add_term_l7),
    )

    cocotb.log.info(
        "constrained_random_ipg_restart_test seed=0x%08X trials=%d max_idle_blocks=%d",
        seed,
        trials,
        max_idle_blocks,
    )

    await seq.add_sof_l0()
    initial_start_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["bytes_valid"] == _START_BYTES_VALID[seq.SOF_L0] for sample in initial_start_phase), (
        "Expected initial SOF_L0 to enter a frame before constrained-random IPG trials"
    )

    for trial_idx in range(trials):
        term_block_type, term_helper = rng.choice(term_helpers)
        start_block_type, start_helper = rng.choice(start_helpers)
        idle_count = rng.randint(0, max_idle_blocks)
        expected_legal = _restart_ipg_is_legal(
            term_block_type=term_block_type,
            idle_count=idle_count,
            start_block_type=start_block_type,
        )
        expected_start_mask = _START_BYTES_VALID[start_block_type]

        if trial_idx < 10 or (trial_idx % 16 == 0):
            cocotb.log.info(
                "ipg-trial=%02d term=0x%02X idle_blocks=%d start=0x%02X legal=%d",
                trial_idx,
                term_block_type,
                idle_count,
                start_block_type,
                int(expected_legal),
            )

        await term_helper()
        await seq.add_manual_idle_chunk(count=idle_count)
        await start_helper()
        restart_phase = await _drain_driver_and_capture(testbase)

        if expected_legal:
            assert all(sample["drop_frame"] == 0 for sample in restart_phase), (
                f"Expected legal IPG restart to avoid drop_frame_o "
                f"(term=0x{term_block_type:02X}, idle_blocks={idle_count}, start=0x{start_block_type:02X})"
            )
            assert any(sample["bytes_valid"] == expected_start_mask for sample in restart_phase), (
                f"Expected legal IPG restart to emit the start bytes_valid mask "
                f"(term=0x{term_block_type:02X}, idle_blocks={idle_count}, start=0x{start_block_type:02X})"
            )
            await seq.add_term_l7()
            _ = await _drain_driver_and_capture(testbase)
        else:
            assert any(sample["drop_frame"] == 1 for sample in restart_phase), (
                f"Expected IPG violation to pulse drop_frame_o "
                f"(term=0x{term_block_type:02X}, idle_blocks={idle_count}, start=0x{start_block_type:02X})"
            )
            assert all(sample["bytes_valid"] != expected_start_mask for sample in restart_phase), (
                f"Expected violating start to be suppressed "
                f"(term=0x{term_block_type:02X}, idle_blocks={idle_count}, start=0x{start_block_type:02X})"
            )

        await seq.add_manual_idle_chunk(count=2)
        await seq.add_sof_l0()
        recovery_phase = await _drain_driver_and_capture(testbase)
        assert any(sample["bytes_valid"] == _START_BYTES_VALID[seq.SOF_L0] for sample in recovery_phase), (
            "Expected deterministic SOF_L0 recovery after restoring a legal IPG"
        )

    await seq.add_term_l7()
    await _finalize_and_check(testbase)


@cocotb.test()
async def edge_case_out_of_frame_nonstart_controls_ignored_test(dut):
    await initialize_tb(dut, clk_period_ns=_env_int("EA_CLK_PERIOD_NS", 10))
    testbase = EthernetAssemblerTestBase(dut)
    seq = testbase.sequence
    rng = random.Random(_env_int("EA_EDGE_IDLE_NONSTART_SEED", 0xA11CE005))

    non_start_actions = (
        lambda: seq.add_term_l0(),
        lambda: seq.add_term_l7(),
        lambda: seq.add_idle_blk(),
        lambda: seq.add_os_d6(),
        lambda: seq.add_os_d5(),
        lambda: seq.add_os_d3t(),
        lambda: seq.add_os_d3b(),
    )

    for _ in range(3):
        for action in non_start_actions:
            await action()

        unknown_block = _pick_unknown_control_block_type(seq, rng)
        await seq.add_control_header(
            payload=seq._compose_control_payload(
                block_type=unknown_block,
                payload_low=rng.getrandbits(seq.CONTROL_DATA_W),
            ),
            in_valid=True,
            locked=True,
            cancel_frame=False,
        )

        await seq.add_random_data(
            in_valid=True,
            locked=True,
            cancel_frame=False,
            rng=rng,
        )

    idle_phase = await _drain_driver_and_capture(testbase)
    assert all(sample["out_valid"] == 0 for sample in idle_phase), (
        "Expected no valid output when only non-start symbols are seen out-of-frame"
    )
    assert all(sample["drop_frame"] == 0 for sample in idle_phase), (
        "Expected no drop_frame_o pulse for non-start out-of-frame symbols"
    )

    await seq.add_random_start(rng=rng)
    recovery_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["out_valid"] == 1 for sample in recovery_phase), (
        "Expected valid output once a proper start frame is received"
    )

    await seq.add_random_end(rng=rng)
    await _finalize_and_check(testbase)
