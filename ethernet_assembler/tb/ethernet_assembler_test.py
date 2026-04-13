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

    for _ in range(frame_count):
        await seq.add_random_start(rng=rng)
        for _ in range(rng.randint(0, max_extra_data)):
            await seq.add_random_data(rng=rng)
        await seq.add_random_end(rng=rng)

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

    await seq.add_random_start(rng=rng)
    recovery_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["out_valid"] == 1 for sample in recovery_phase), (
        "Expected out_valid_o recovery after fresh start frame"
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

    await seq.add_random_start(rng=rng)
    recovery_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["out_valid"] == 1 for sample in recovery_phase), (
        "Expected output recovery after valid start frame"
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

    await seq.add_sof_l0(in_valid=True, locked=True, cancel_frame=False)
    recovered_phase = await _drain_driver_and_capture(testbase)
    assert any(sample["out_valid"] == 1 for sample in recovered_phase), (
        "Expected recovery on first qualified SOF after cancel drop"
    )

    await seq.add_random_end(rng=rng)
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
