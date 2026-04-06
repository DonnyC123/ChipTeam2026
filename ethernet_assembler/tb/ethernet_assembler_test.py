import os
import random
from dataclasses import dataclass

import cocotb
from cocotb.triggers import RisingEdge, Timer

from ethernet_assembler.tb.ethernet_assembler_sequence import EthernetAssemblerSequence
from ethernet_assembler.tb.ethernet_assembler_sequence_item import EthernetAssemblerSequenceItem
from ethernet_assembler.tb.ethernet_assembler_test_base import EthernetAssemblerTestBase
from tb_utils.tb_common import initialize_tb, reset_dut

HEADER_W = EthernetAssemblerSequence.HEADER_W
PAYLOAD_W = EthernetAssemblerSequence.PAYLOAD_W
BLOCK_TYPE_W = EthernetAssemblerSequence.BLOCK_TYPE_W
CONTROL_DATA_W = PAYLOAD_W - BLOCK_TYPE_W
PAYLOAD_MASK = (1 << PAYLOAD_W) - 1

DATA_HDR = EthernetAssemblerSequence.DATA_SYNC_HEADER
CTRL_HDR = EthernetAssemblerSequence.CONTROL_SYNC_HEADER
BAD_HDR_00 = EthernetAssemblerSequence.SYNC_HEADER_BAD1
BAD_HDR_11 = EthernetAssemblerSequence.SYNC_HEADER_BAD2

SOF_L0 = EthernetAssemblerSequence.START_BLOCKS[0]
SOF_L4 = EthernetAssemblerSequence.START_BLOCKS[4]
TERM_L0 = EthernetAssemblerSequence.TERM_BLOCKS[0]
TERM_L7 = EthernetAssemblerSequence.TERM_BLOCKS[7]
IDLE_BLK = EthernetAssemblerSequence.IDLE_BLOCK

TERM_VALID_MASKS = {
    EthernetAssemblerSequence.TERM_BLOCKS[0]: 0x00,
    EthernetAssemblerSequence.TERM_BLOCKS[1]: 0x40,
    EthernetAssemblerSequence.TERM_BLOCKS[2]: 0x60,
    EthernetAssemblerSequence.TERM_BLOCKS[3]: 0x70,
    EthernetAssemblerSequence.TERM_BLOCKS[4]: 0x78,
    EthernetAssemblerSequence.TERM_BLOCKS[5]: 0x7C,
    EthernetAssemblerSequence.TERM_BLOCKS[6]: 0x7E,
    EthernetAssemblerSequence.TERM_BLOCKS[7]: 0x7F,
}

ORDERED_SET_VALID_MASKS = {
    EthernetAssemblerSequence.ORDERED_SET_BLOCKS["OS_D6"]: 0x77,
    EthernetAssemblerSequence.ORDERED_SET_BLOCKS["OS_D5"]: 0x77,
    EthernetAssemblerSequence.ORDERED_SET_BLOCKS["OS_D3T"]: 0x70,
    EthernetAssemblerSequence.ORDERED_SET_BLOCKS["OS_D3B"]: 0x07,
}

CONTRACT_MATRIX = {
    "idle": {
        "data": {"drop_frame": 0, "out_valid": 0, "bytes_valid": 0x00, "next_state": "idle"},
        "term": {"drop_frame": 0, "out_valid": 0, "bytes_valid": 0x00, "next_state": "idle"},
        "start_l0": {
            "drop_frame": 0,
            "out_valid": 1,
            "bytes_valid": 0x7F,
            "next_state": "in_frame",
        },
        "start_l4": {
            "drop_frame": 0,
            "out_valid": 1,
            "bytes_valid": 0x07,
            "next_state": "in_frame",
        },
    },
    "in_frame": {
        "data": {"drop_frame": 0, "out_valid": 1, "bytes_valid": 0xFF, "next_state": "in_frame"},
        "term_l7": {
            "drop_frame": 0,
            "out_valid": 1,
            "bytes_valid": 0x7F,
            "next_state": "idle",
        },
        "double_sof": {
            "drop_frame": 1,
            "out_valid": 0,
            "bytes_valid": 0x00,
            "next_state": "idle",
        },
        "idle_corrupt": {
            "drop_frame": 1,
            "out_valid": 0,
            "bytes_valid": 0x00,
            "next_state": "idle",
        },
        "unknown_corrupt": {
            "drop_frame": 1,
            "out_valid": 0,
            "bytes_valid": 0x00,
            "next_state": "idle",
        },
        "bad_header": {
            "drop_frame": 1,
            "out_valid": 0,
            "bytes_valid": 0x00,
            "next_state": "idle",
        },
        "cancel": {
            "drop_frame": None,
            "out_valid": 0,
            "bytes_valid": 0x00,
            "next_state": "cancel_suppressed",
        },
    },
    "cancel_suppressed": {
        "any_while_cancel_high": {
            "drop_frame": None,
            "out_valid": 0,
            "bytes_valid": 0x00,
            "next_state": "cancel_suppressed",
        },
        "cancel_low_non_sof": {
            "drop_frame": 0,
            "out_valid": 0,
            "bytes_valid": 0x00,
            "next_state": "cancel_suppressed",
        },
        "cancel_low_sof_l0": {
            "drop_frame": 0,
            "out_valid": 1,
            "bytes_valid": 0x7F,
            "next_state": "in_frame",
        },
        "cancel_low_sof_l4": {
            "drop_frame": 0,
            "out_valid": 1,
            "bytes_valid": 0x07,
            "next_state": "in_frame",
        },
    },
}


@dataclass
class ContractState:
    in_frame: bool = False
    cancel_suppressed: bool = False


def _compose_control_payload(block_type: int, payload_low: int = 0) -> int:
    payload_low_mask = (1 << CONTROL_DATA_W) - 1
    return ((block_type & 0xFF) << CONTROL_DATA_W) | (payload_low & payload_low_mask)


def _compose_raw_block(sync_header: int, payload: int) -> int:
    return ((sync_header & ((1 << HEADER_W) - 1)) << PAYLOAD_W) | (payload & PAYLOAD_MASK)


def _to_network_input(raw_input_data: int) -> int:
    return EthernetAssemblerSequenceItem._to_network_order(raw_input_data)


async def _prime_inputs(dut):
    dut.input_data_i.value = 0
    dut.in_valid_i.value = 0
    dut.locked_i.value = 1
    dut.cancel_frame_i.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")


async def _drive_block(
    dut,
    *,
    sync_header: int,
    payload: int,
    in_valid: bool = True,
    locked: bool = True,
    cancel_frame: bool = False,
):
    raw_input_data = _compose_raw_block(sync_header=sync_header, payload=payload)
    dut.input_data_i.value = _to_network_input(raw_input_data)
    dut.in_valid_i.value = int(in_valid)
    dut.locked_i.value = int(locked)
    dut.cancel_frame_i.value = int(cancel_frame)

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    obs = {
        "drop_frame": int(dut.drop_frame_o.value),
        "out_valid": int(dut.out_valid_o.value),
        "bytes_valid": int(dut.bytes_valid_o.value),
    }
    return obs


async def _drive_control(
    dut,
    *,
    block_type: int,
    payload_low: int = 0,
    in_valid: bool = True,
    locked: bool = True,
    cancel_frame: bool = False,
):
    payload = _compose_control_payload(block_type=block_type, payload_low=payload_low)
    return await _drive_block(
        dut,
        sync_header=CTRL_HDR,
        payload=payload,
        in_valid=in_valid,
        locked=locked,
        cancel_frame=cancel_frame,
    )


async def _drive_data(
    dut,
    *,
    payload: int,
    in_valid: bool = True,
    locked: bool = True,
    cancel_frame: bool = False,
):
    return await _drive_block(
        dut,
        sync_header=DATA_HDR,
        payload=payload,
        in_valid=in_valid,
        locked=locked,
        cancel_frame=cancel_frame,
    )


def _assert_observation(
    obs: dict,
    *,
    label: str,
    drop_frame: int | None = None,
    out_valid: int | None = None,
    bytes_valid: int | None = None,
):
    if drop_frame is not None:
        assert obs["drop_frame"] == drop_frame, (
            f"{label}: drop_frame mismatch (expected {drop_frame}, got {obs['drop_frame']})"
        )

    if out_valid is not None:
        assert obs["out_valid"] == out_valid, (
            f"{label}: out_valid mismatch (expected {out_valid}, got {obs['out_valid']})"
        )

    if bytes_valid is not None:
        assert obs["bytes_valid"] == bytes_valid, (
            f"{label}: bytes_valid mismatch (expected 0x{bytes_valid:02X}, got 0x{obs['bytes_valid']:02X})"
        )


def _assert_from_contract_matrix(obs: dict, *, state: str, stimulus: str, label: str):
    expected = CONTRACT_MATRIX[state][stimulus]
    _assert_observation(
        obs,
        label=label,
        drop_frame=expected["drop_frame"],
        out_valid=expected["out_valid"],
        bytes_valid=expected["bytes_valid"],
    )


def _log_trace(seed: int, step: int, action: str, obs: dict, state: ContractState):
    cocotb.log.info(
        "seed=0x%08X step=%04d action=%s -> drop=%d out_valid=%d bytes_valid=0x%02X (in_frame=%d cancel_suppressed=%d)",
        seed,
        step,
        action,
        obs["drop_frame"],
        obs["out_valid"],
        obs["bytes_valid"],
        int(state.in_frame),
        int(state.cancel_suppressed),
    )


def _pick_invalid_control_block_type(rng: random.Random) -> int:
    while True:
        candidate = rng.getrandbits(BLOCK_TYPE_W)
        if candidate not in EthernetAssemblerSequence.VALID_CONTROL_BLOCK_TYPES:
            return candidate


@cocotb.test()
async def contract_matrix_direct_test(dut):
    await initialize_tb(dut, clk_period_ns=10)
    await _prime_inputs(dut)

    obs = await _drive_data(dut, payload=0x0102030405060708)
    _assert_from_contract_matrix(obs, state="idle", stimulus="data", label="idle_data")

    obs = await _drive_control(dut, block_type=TERM_L0, payload_low=0x1020304050607)
    _assert_from_contract_matrix(obs, state="idle", stimulus="term", label="idle_term")

    obs = await _drive_control(dut, block_type=SOF_L0, payload_low=0x11223344556677)
    _assert_from_contract_matrix(obs, state="idle", stimulus="start_l0", label="idle_sof_l0")

    obs = await _drive_data(dut, payload=0x2122232425262728)
    _assert_from_contract_matrix(obs, state="in_frame", stimulus="data", label="in_frame_data")

    obs = await _drive_control(dut, block_type=TERM_L7, payload_low=0x31323334353637)
    _assert_from_contract_matrix(obs, state="in_frame", stimulus="term_l7", label="in_frame_term_l7")

    # Double-end out-of-frame must be ignored.
    obs = await _drive_control(dut, block_type=TERM_L7, payload_low=0x41424344454647)
    _assert_from_contract_matrix(obs, state="idle", stimulus="term", label="idle_double_term")

    await reset_dut(dut, 20)
    await _prime_inputs(dut)
    obs = await _drive_control(dut, block_type=SOF_L4, payload_low=0x51525354555657)
    _assert_from_contract_matrix(obs, state="idle", stimulus="start_l4", label="idle_sof_l4")


@cocotb.test()
async def corruption_drop_single_pulse_test(dut):
    await initialize_tb(dut, clk_period_ns=10)
    await _prime_inputs(dut)

    # Back-to-back double start: drop once on first corruption offense.
    obs = await _drive_control(dut, block_type=SOF_L0, payload_low=0x01020304050607)
    _assert_observation(obs, label="bb_sof0", drop_frame=0, out_valid=1, bytes_valid=0x7F)

    obs = await _drive_control(dut, block_type=SOF_L4, payload_low=0x11121314151617)
    _assert_observation(obs, label="bb_sof1_corrupt", drop_frame=1, out_valid=0, bytes_valid=0x00)

    obs = await _drive_control(dut, block_type=IDLE_BLK, payload_low=0x21222324252627)
    _assert_observation(obs, label="bb_post_corrupt_idle", drop_frame=0, out_valid=0, bytes_valid=0x00)

    obs = await _drive_control(dut, block_type=SOF_L0, payload_low=0x31323334353637)
    _assert_observation(obs, label="bb_recover_sof", drop_frame=0, out_valid=1, bytes_valid=0x7F)

    # Spaced double start corruption.
    await reset_dut(dut, 20)
    await _prime_inputs(dut)
    await _drive_control(dut, block_type=SOF_L0, payload_low=0x41424344454647)
    await _drive_data(dut, payload=0x5152535455565758)

    obs = await _drive_control(dut, block_type=SOF_L4, payload_low=0x61626364656667)
    _assert_observation(obs, label="spaced_double_sof", drop_frame=1, out_valid=0, bytes_valid=0x00)

    obs = await _drive_data(dut, payload=0x7172737475767778)
    _assert_observation(obs, label="spaced_post_corrupt_data", drop_frame=0, out_valid=0, bytes_valid=0x00)

    # In-frame junk/unknown/bad-header each cause one corruption drop and end frame.
    await reset_dut(dut, 20)
    await _prime_inputs(dut)
    await _drive_control(dut, block_type=SOF_L0, payload_low=0x81828384858687)

    obs = await _drive_control(dut, block_type=IDLE_BLK, payload_low=0x91929394959697)
    _assert_observation(obs, label="in_frame_idle_corrupt", drop_frame=1, out_valid=0, bytes_valid=0x00)

    obs = await _drive_control(dut, block_type=0x12, payload_low=0xA1A2A3A4A5A6A7)
    _assert_observation(obs, label="post_idle_unknown_no_extra_drop", drop_frame=0, out_valid=0, bytes_valid=0x00)

    await reset_dut(dut, 20)
    await _prime_inputs(dut)
    await _drive_control(dut, block_type=SOF_L0, payload_low=0xB1B2B3B4B5B6B7)

    obs = await _drive_control(dut, block_type=0x12, payload_low=0xC1C2C3C4C5C6C7)
    _assert_observation(obs, label="in_frame_unknown_corrupt", drop_frame=1, out_valid=0, bytes_valid=0x00)

    obs = await _drive_block(dut, sync_header=BAD_HDR_00, payload=0xD1D2D3D4D5D6D7D8)
    _assert_observation(obs, label="post_unknown_bad_hdr_no_extra_drop", drop_frame=0, out_valid=0, bytes_valid=0x00)

    await reset_dut(dut, 20)
    await _prime_inputs(dut)
    await _drive_control(dut, block_type=SOF_L0, payload_low=0xE1E2E3E4E5E6E7)

    obs = await _drive_block(dut, sync_header=BAD_HDR_11, payload=0xF1F2F3F4F5F6F7F8)
    _assert_observation(obs, label="in_frame_bad_header_corrupt", drop_frame=1, out_valid=0, bytes_valid=0x00)

    obs = await _drive_control(dut, block_type=TERM_L7, payload_low=0x01020304050607)
    _assert_observation(obs, label="post_bad_header_term_no_extra_drop", drop_frame=0, out_valid=0, bytes_valid=0x00)


@cocotb.test()
async def cancel_suppression_contract_test(dut):
    await initialize_tb(dut, clk_period_ns=10)
    await _prime_inputs(dut)

    # Enter frame and stream payload.
    obs = await _drive_control(dut, block_type=SOF_L0, payload_low=0x01020304050607)
    _assert_observation(obs, label="cancel_sof", drop_frame=0, out_valid=1, bytes_valid=0x7F)

    obs = await _drive_data(dut, payload=0x1112131415161718)
    _assert_observation(obs, label="cancel_data_before", drop_frame=0, out_valid=1, bytes_valid=0xFF)

    # Canceled cycles do not constrain drop_frame.
    obs = await _drive_data(dut, payload=0x2122232425262728, cancel_frame=True)
    _assert_from_contract_matrix(obs, state="in_frame", stimulus="cancel", label="cancel_in_frame_single_pulse")

    # Held-high cancel suppresses all outputs, including SOF.
    obs = await _drive_data(dut, payload=0x3132333435363738, cancel_frame=True)
    _assert_from_contract_matrix(
        obs,
        state="cancel_suppressed",
        stimulus="any_while_cancel_high",
        label="cancel_high_data",
    )

    obs = await _drive_control(dut, block_type=SOF_L0, payload_low=0x41424344454647, cancel_frame=True)
    _assert_from_contract_matrix(
        obs,
        state="cancel_suppressed",
        stimulus="any_while_cancel_high",
        label="cancel_high_sof",
    )

    # Cancel low but no new SOF still suppressed.
    obs = await _drive_data(dut, payload=0x5152535455565758, cancel_frame=False)
    _assert_from_contract_matrix(
        obs,
        state="cancel_suppressed",
        stimulus="cancel_low_non_sof",
        label="cancel_low_data_no_sof",
    )

    # Recovery requires fresh uncanceled SOF.
    obs = await _drive_control(dut, block_type=SOF_L4, payload_low=0x61626364656667, cancel_frame=False)
    _assert_from_contract_matrix(
        obs,
        state="cancel_suppressed",
        stimulus="cancel_low_sof_l4",
        label="cancel_recover_sof_l4",
    )

    obs = await _drive_data(dut, payload=0x7172737475767778, cancel_frame=False)
    _assert_observation(obs, label="cancel_recover_data", drop_frame=0, out_valid=1, bytes_valid=0xFF)

    # Single-cycle cancel pulse still requires SOF-based recovery.
    await reset_dut(dut, 20)
    await _prime_inputs(dut)
    await _drive_control(dut, block_type=SOF_L0, payload_low=0x81828384858687)
    await _drive_data(dut, payload=0x9192939495969798)

    obs = await _drive_data(dut, payload=0xA1A2A3A4A5A6A7A8, cancel_frame=True)
    _assert_observation(obs, label="cancel_single_cycle", out_valid=0, bytes_valid=0x00)

    obs = await _drive_data(dut, payload=0xB1B2B3B4B5B6B7B8, cancel_frame=False)
    _assert_observation(obs, label="cancel_single_cycle_post_data", drop_frame=0, out_valid=0, bytes_valid=0x00)

    obs = await _drive_control(dut, block_type=SOF_L0, payload_low=0xC1C2C3C4C5C6C7, cancel_frame=False)
    _assert_observation(obs, label="cancel_single_cycle_recover", drop_frame=0, out_valid=1, bytes_valid=0x7F)


@cocotb.test()
async def constrained_random_contract_invariant_test(dut):
    await initialize_tb(dut, clk_period_ns=10)
    await _prime_inputs(dut)

    seed = int(os.getenv("EA_RANDOM_SEED", "305419896"), 0)
    num_steps = int(os.getenv("EA_RANDOM_STEPS", "1500"), 0)
    rng = random.Random(seed)
    state = ContractState()

    cocotb.log.info("Starting constrained-random audit: seed=0x%08X steps=%d", seed, num_steps)

    for step in range(num_steps):
        action = ""
        obs = None

        if state.cancel_suppressed:
            roll = rng.random()
            if roll < 0.30:
                action = "cancel_high_data"
                obs = await _drive_data(dut, payload=rng.getrandbits(PAYLOAD_W), cancel_frame=True)
                _assert_observation(obs, label=action, out_valid=0, bytes_valid=0x00)
            elif roll < 0.55:
                action = "cancel_high_sof"
                obs = await _drive_control(
                    dut,
                    block_type=rng.choice((SOF_L0, SOF_L4)),
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                    cancel_frame=True,
                )
                _assert_observation(obs, label=action, out_valid=0, bytes_valid=0x00)
            elif roll < 0.80:
                action = "cancel_low_non_sof"
                obs = await _drive_data(dut, payload=rng.getrandbits(PAYLOAD_W), cancel_frame=False)
                _assert_observation(obs, label=action, drop_frame=0, out_valid=0, bytes_valid=0x00)
            else:
                lane = rng.choice((0, 4))
                action = f"cancel_recover_sof_l{lane}"
                obs = await _drive_control(
                    dut,
                    block_type=EthernetAssemblerSequence.START_BLOCKS[lane],
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                    cancel_frame=False,
                )
                expected_mask = 0x7F if lane == 0 else 0x07
                _assert_observation(obs, label=action, drop_frame=0, out_valid=1, bytes_valid=expected_mask)
                state.cancel_suppressed = False
                state.in_frame = True

        elif state.in_frame:
            roll = rng.random()
            if roll < 0.32:
                action = "in_frame_data"
                obs = await _drive_data(dut, payload=rng.getrandbits(PAYLOAD_W))
                _assert_observation(obs, label=action, drop_frame=0, out_valid=1, bytes_valid=0xFF)
            elif roll < 0.48:
                action = "in_frame_term"
                term_block = rng.choice(tuple(EthernetAssemblerSequence.TERM_BLOCKS.values()))
                obs = await _drive_control(
                    dut,
                    block_type=term_block,
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                )
                _assert_observation(
                    obs,
                    label=action,
                    drop_frame=0,
                    out_valid=int(TERM_VALID_MASKS[term_block] != 0),
                    bytes_valid=TERM_VALID_MASKS[term_block],
                )
                state.in_frame = False
            elif roll < 0.63:
                action = "in_frame_ordered_set"
                os_block = rng.choice(tuple(ORDERED_SET_VALID_MASKS))
                obs = await _drive_control(
                    dut,
                    block_type=os_block,
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                )
                _assert_observation(
                    obs,
                    label=action,
                    drop_frame=0,
                    out_valid=1,
                    bytes_valid=ORDERED_SET_VALID_MASKS[os_block],
                )
            elif roll < 0.74:
                action = "in_frame_double_sof_corrupt"
                obs = await _drive_control(
                    dut,
                    block_type=rng.choice((SOF_L0, SOF_L4)),
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                )
                _assert_observation(obs, label=action, drop_frame=1, out_valid=0, bytes_valid=0x00)
                state.in_frame = False
            elif roll < 0.84:
                action = "in_frame_idle_corrupt"
                obs = await _drive_control(dut, block_type=IDLE_BLK, payload_low=rng.getrandbits(CONTROL_DATA_W))
                _assert_observation(obs, label=action, drop_frame=1, out_valid=0, bytes_valid=0x00)
                state.in_frame = False
            elif roll < 0.92:
                action = "in_frame_unknown_corrupt"
                obs = await _drive_control(dut, block_type=0x12, payload_low=rng.getrandbits(CONTROL_DATA_W))
                _assert_observation(obs, label=action, drop_frame=1, out_valid=0, bytes_valid=0x00)
                state.in_frame = False
            elif roll < 0.97:
                action = "in_frame_bad_header_corrupt"
                bad_hdr = rng.choice((BAD_HDR_00, BAD_HDR_11))
                obs = await _drive_block(
                    dut,
                    sync_header=bad_hdr,
                    payload=rng.getrandbits(PAYLOAD_W),
                )
                _assert_observation(obs, label=action, drop_frame=1, out_valid=0, bytes_valid=0x00)
                state.in_frame = False
            else:
                action = "in_frame_cancel"
                obs = await _drive_data(
                    dut,
                    payload=rng.getrandbits(PAYLOAD_W),
                    cancel_frame=True,
                )
                _assert_observation(obs, label=action, out_valid=0, bytes_valid=0x00)
                state.in_frame = False
                state.cancel_suppressed = True

        else:
            roll = rng.random()
            if roll < 0.40:
                lane = rng.choice((0, 4))
                action = f"idle_sof_l{lane}"
                obs = await _drive_control(
                    dut,
                    block_type=EthernetAssemblerSequence.START_BLOCKS[lane],
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                )
                expected_mask = 0x7F if lane == 0 else 0x07
                _assert_observation(obs, label=action, drop_frame=0, out_valid=1, bytes_valid=expected_mask)
                state.in_frame = True
            elif roll < 0.65:
                action = "idle_data"
                obs = await _drive_data(dut, payload=rng.getrandbits(PAYLOAD_W))
                _assert_observation(obs, label=action, drop_frame=0, out_valid=0, bytes_valid=0x00)
            elif roll < 0.85:
                action = "idle_term"
                obs = await _drive_control(
                    dut,
                    block_type=rng.choice(tuple(EthernetAssemblerSequence.TERM_BLOCKS.values())),
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                )
                _assert_observation(obs, label=action, drop_frame=0, out_valid=0, bytes_valid=0x00)
            else:
                action = "idle_cancel"
                obs = await _drive_data(
                    dut,
                    payload=rng.getrandbits(PAYLOAD_W),
                    cancel_frame=True,
                )
                _assert_observation(obs, label=action, out_valid=0, bytes_valid=0x00)

        if step < 24 or step % 128 == 0:
            _log_trace(seed, step, action, obs, state)


@cocotb.test()
async def constrained_random_qualifier_stress_test(dut):
    await initialize_tb(dut, clk_period_ns=10)
    await _prime_inputs(dut)

    seed = int(os.getenv("EA_QUALIFIER_RANDOM_SEED", "2779096485"), 0)
    num_steps = int(os.getenv("EA_QUALIFIER_RANDOM_STEPS", "1800"), 0)
    rng = random.Random(seed)
    state = ContractState()

    cocotb.log.info(
        "Starting qualifier-focused constrained-random audit: seed=0x%08X steps=%d",
        seed,
        num_steps,
    )

    for step in range(num_steps):
        action = ""
        obs = None

        if state.cancel_suppressed:
            roll = rng.random()
            if roll < 0.28:
                action = "drop_mode_cancel_high_data"
                obs = await _drive_data(
                    dut,
                    payload=rng.getrandbits(PAYLOAD_W),
                    in_valid=rng.choice((False, True)),
                    locked=rng.choice((False, True)),
                    cancel_frame=True,
                )
                _assert_observation(obs, label=action, drop_frame=0, out_valid=0, bytes_valid=0x00)
            elif roll < 0.54:
                action = "drop_mode_cancel_low_non_sof"
                if rng.random() < 0.5:
                    obs = await _drive_data(
                        dut,
                        payload=rng.getrandbits(PAYLOAD_W),
                        in_valid=True,
                        locked=True,
                        cancel_frame=False,
                    )
                else:
                    obs = await _drive_control(
                        dut,
                        block_type=rng.choice(
                            (
                                IDLE_BLK,
                                TERM_L7,
                                _pick_invalid_control_block_type(rng),
                            )
                        ),
                        payload_low=rng.getrandbits(CONTROL_DATA_W),
                        in_valid=True,
                        locked=True,
                        cancel_frame=False,
                    )
                _assert_observation(obs, label=action, drop_frame=0, out_valid=0, bytes_valid=0x00)
            elif roll < 0.76:
                action = "drop_mode_sof_blocked_by_qualifier"
                in_valid = rng.choice((False, True))
                locked = rng.choice((False, True))
                if in_valid and locked:
                    locked = False
                lane = rng.choice((0, 4))
                obs = await _drive_control(
                    dut,
                    block_type=EthernetAssemblerSequence.START_BLOCKS[lane],
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                    in_valid=in_valid,
                    locked=locked,
                    cancel_frame=False,
                )
                _assert_observation(obs, label=action, drop_frame=0, out_valid=0, bytes_valid=0x00)
            else:
                lane = rng.choice((0, 4))
                action = f"drop_mode_recover_sof_l{lane}"
                obs = await _drive_control(
                    dut,
                    block_type=EthernetAssemblerSequence.START_BLOCKS[lane],
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                    in_valid=True,
                    locked=True,
                    cancel_frame=False,
                )
                expected_mask = 0x7F if lane == 0 else 0x07
                _assert_observation(obs, label=action, drop_frame=0, out_valid=1, bytes_valid=expected_mask)
                state.cancel_suppressed = False
                state.in_frame = True

        elif state.in_frame:
            roll = rng.random()
            if roll < 0.20:
                action = "in_frame_data"
                obs = await _drive_data(dut, payload=rng.getrandbits(PAYLOAD_W))
                _assert_observation(obs, label=action, drop_frame=0, out_valid=1, bytes_valid=0xFF)
            elif roll < 0.34:
                action = "in_frame_ordered_set"
                os_block = rng.choice(tuple(ORDERED_SET_VALID_MASKS))
                obs = await _drive_control(
                    dut,
                    block_type=os_block,
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                )
                _assert_observation(
                    obs,
                    label=action,
                    drop_frame=0,
                    out_valid=1,
                    bytes_valid=ORDERED_SET_VALID_MASKS[os_block],
                )
            elif roll < 0.48:
                action = "in_frame_term"
                term_block = rng.choice(tuple(EthernetAssemblerSequence.TERM_BLOCKS.values()))
                obs = await _drive_control(
                    dut,
                    block_type=term_block,
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                )
                _assert_observation(
                    obs,
                    label=action,
                    drop_frame=0,
                    out_valid=int(TERM_VALID_MASKS[term_block] != 0),
                    bytes_valid=TERM_VALID_MASKS[term_block],
                )
                state.in_frame = False
            elif roll < 0.62:
                action = "in_frame_in_valid_low_hold"
                obs = await _drive_data(
                    dut,
                    payload=rng.getrandbits(PAYLOAD_W),
                    in_valid=False,
                    locked=True,
                    cancel_frame=False,
                )
                _assert_observation(obs, label=action, drop_frame=0, out_valid=0, bytes_valid=0x00)
            elif roll < 0.74:
                action = "in_frame_lock_loss_drop"
                obs = await _drive_data(
                    dut,
                    payload=rng.getrandbits(PAYLOAD_W),
                    in_valid=rng.choice((False, True)),
                    locked=False,
                    cancel_frame=False,
                )
                _assert_observation(obs, label=action, drop_frame=1, out_valid=0, bytes_valid=0x00)
                state.in_frame = False
            elif roll < 0.85:
                action = "in_frame_bad_header_drop"
                obs = await _drive_block(
                    dut,
                    sync_header=rng.choice((BAD_HDR_00, BAD_HDR_11)),
                    payload=rng.getrandbits(PAYLOAD_W),
                    in_valid=rng.choice((False, True)),
                    locked=True,
                    cancel_frame=False,
                )
                _assert_observation(obs, label=action, drop_frame=1, out_valid=0, bytes_valid=0x00)
                state.in_frame = False
            elif roll < 0.93:
                action = "in_frame_unknown_control_drop"
                obs = await _drive_control(
                    dut,
                    block_type=_pick_invalid_control_block_type(rng),
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                    in_valid=True,
                    locked=True,
                    cancel_frame=False,
                )
                _assert_observation(obs, label=action, drop_frame=1, out_valid=0, bytes_valid=0x00)
                state.in_frame = False
            else:
                action = "in_frame_cancel"
                obs = await _drive_data(
                    dut,
                    payload=rng.getrandbits(PAYLOAD_W),
                    in_valid=rng.choice((False, True)),
                    locked=rng.choice((False, True)),
                    cancel_frame=True,
                )
                _assert_observation(obs, label=action, drop_frame=1, out_valid=0, bytes_valid=0x00)
                state.in_frame = False
                state.cancel_suppressed = True

        else:
            roll = rng.random()
            if roll < 0.24:
                lane = rng.choice((0, 4))
                action = f"idle_sof_l{lane}"
                obs = await _drive_control(
                    dut,
                    block_type=EthernetAssemblerSequence.START_BLOCKS[lane],
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                    in_valid=True,
                    locked=True,
                    cancel_frame=False,
                )
                expected_mask = 0x7F if lane == 0 else 0x07
                _assert_observation(obs, label=action, drop_frame=0, out_valid=1, bytes_valid=expected_mask)
                state.in_frame = True
            elif roll < 0.43:
                action = "idle_data"
                obs = await _drive_data(dut, payload=rng.getrandbits(PAYLOAD_W))
                _assert_observation(obs, label=action, drop_frame=0, out_valid=0, bytes_valid=0x00)
            elif roll < 0.58:
                action = "idle_term"
                obs = await _drive_control(
                    dut,
                    block_type=rng.choice(tuple(EthernetAssemblerSequence.TERM_BLOCKS.values())),
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                )
                _assert_observation(obs, label=action, drop_frame=0, out_valid=0, bytes_valid=0x00)
            elif roll < 0.70:
                lane = rng.choice((0, 4))
                action = f"idle_sof_l{lane}_in_valid_low"
                obs = await _drive_control(
                    dut,
                    block_type=EthernetAssemblerSequence.START_BLOCKS[lane],
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                    in_valid=False,
                    locked=True,
                    cancel_frame=False,
                )
                _assert_observation(obs, label=action, drop_frame=0, out_valid=0, bytes_valid=0x00)
            elif roll < 0.80:
                lane = rng.choice((0, 4))
                action = f"idle_sof_l{lane}_locked_low"
                obs = await _drive_control(
                    dut,
                    block_type=EthernetAssemblerSequence.START_BLOCKS[lane],
                    payload_low=rng.getrandbits(CONTROL_DATA_W),
                    in_valid=True,
                    locked=False,
                    cancel_frame=False,
                )
                _assert_observation(obs, label=action, drop_frame=0, out_valid=0, bytes_valid=0x00)
            elif roll < 0.90:
                action = "idle_cancel"
                if rng.random() < 0.5:
                    obs = await _drive_data(
                        dut,
                        payload=rng.getrandbits(PAYLOAD_W),
                        in_valid=rng.choice((False, True)),
                        locked=rng.choice((False, True)),
                        cancel_frame=True,
                    )
                else:
                    obs = await _drive_control(
                        dut,
                        block_type=EthernetAssemblerSequence.START_BLOCKS[rng.choice((0, 4))],
                        payload_low=rng.getrandbits(CONTROL_DATA_W),
                        in_valid=rng.choice((False, True)),
                        locked=rng.choice((False, True)),
                        cancel_frame=True,
                    )
                _assert_observation(obs, label=action, drop_frame=0, out_valid=0, bytes_valid=0x00)
            else:
                action = "idle_bad_or_unknown_control"
                if rng.random() < 0.5:
                    obs = await _drive_block(
                        dut,
                        sync_header=rng.choice((BAD_HDR_00, BAD_HDR_11)),
                        payload=rng.getrandbits(PAYLOAD_W),
                        in_valid=rng.choice((False, True)),
                        locked=rng.choice((False, True)),
                        cancel_frame=False,
                    )
                else:
                    obs = await _drive_control(
                        dut,
                        block_type=_pick_invalid_control_block_type(rng),
                        payload_low=rng.getrandbits(CONTROL_DATA_W),
                        in_valid=rng.choice((False, True)),
                        locked=rng.choice((False, True)),
                        cancel_frame=False,
                    )
                _assert_observation(obs, label=action, drop_frame=0, out_valid=0, bytes_valid=0x00)

        if step < 24 or step % 128 == 0:
            _log_trace(seed, step, action, obs, state)


@cocotb.test()
async def model_smoke_basic_test(dut):
    if os.getenv("EA_ENABLE_MODEL_SMOKE", "0") != "1":
        cocotb.log.info("Skipping model smoke test (set EA_ENABLE_MODEL_SMOKE=1 to enable)")
        return

    await initialize_tb(dut, clk_period_ns=10)
    testbase = EthernetAssemblerTestBase(dut)

    await testbase.sequence.add_start_block(lane=0, payload_low=0x01020304050607)
    await testbase.sequence.add_data_block(0x1112131415161718)
    await testbase.sequence.add_data_block(0x2122232425262728)
    await testbase.sequence.add_terminate_block(lane=7, payload_low=0x31323334353637)
    await testbase.sequence.add_data_block(0x4142434445464748)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def model_smoke_corruption_helpers_test(dut):
    if os.getenv("EA_ENABLE_MODEL_SMOKE", "0") != "1":
        cocotb.log.info("Skipping model smoke test (set EA_ENABLE_MODEL_SMOKE=1 to enable)")
        return

    await initialize_tb(dut, clk_period_ns=10)
    testbase = EthernetAssemblerTestBase(dut)

    seed = int(os.getenv("EA_SMOKE_SEED", "305419896"), 0)
    rng = random.Random(seed)

    await testbase.sequence.add_start_block(lane=0, payload_low=0x01020304050607)
    await testbase.sequence.add_data_block(0x1112131415161718)
    await testbase.sequence.add_corrupted_block(corruption_kind="bad_header", rng=rng)
    await testbase.sequence.add_start_block(lane=4, payload_low=0x41424344454647)
    await testbase.sequence.add_ordered_set_block(
        os_kind="OS_D6",
        payload_low=0x51525354555657,
    )
    await testbase.sequence.add_corrupted_block(
        corruption_kind="unknown_control",
        invalid_block_type=0x12,
        rng=rng,
    )

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()
