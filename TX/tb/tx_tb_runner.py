import os
from pathlib import Path

import pytest
from cocotb_tools.runner import get_runner

REPO_ROOT = Path(__file__).resolve().parents[2]
TX_DIR = REPO_ROOT / "TX"
TX_TB_DIR = TX_DIR / "tb"
PCS_DIR = TX_DIR / "rtl" / "pcs_generator"


def _pcs_sources() -> list[Path]:
    explicit_first = [
        PCS_DIR / "tx_axis_if.sv",
        PCS_DIR / "pcs_pkg.sv",
        PCS_DIR / "data_pipeline.sv",
    ]
    excluded = {path.name for path in explicit_first}
    excluded.add("pcs_generator_tb_top.sv")
    remaining = sorted(
        path for path in PCS_DIR.glob("*.sv") if path.name not in excluded
    )
    return [path for path in explicit_first if path.exists()] + remaining

sources = [
    TX_DIR / "rtl" / "tx_fifo" / "tx_subsystem_pkg.sv",
    TX_DIR / "rtl" / "tx_fifo" / "tx_async_fifo.sv",
    TX_DIR / "rtl" / "tx_fifo" / "tx_subsystem.sv",
    TX_DIR / "rtl" / "crc_inserter" / "crc_inserter.sv",
    *_pcs_sources(),
    TX_DIR / "rtl" / "scrambler" / "scrambler.sv",
    TX_DIR / "rtl" / "debubbler" / "debubbler.sv",
    TX_TB_DIR / "tx_top.sv",
]

SMOKE_FILTER = (
    "test_single_min_frame|"
    "test_dma_tkeep_tail_lengths|"
    "test_configured_queue_width|"
    "test_invalid_tdest_backpressure_num_queues_3|"
    "test_small_fifo_depth_smoke"
)


def _env_int(name: str, default: int) -> int:
    value = int(os.environ.get(name, default))
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


def _pythonpath() -> str:
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    path_parts = [str(REPO_ROOT), str(TX_DIR), str(TX_TB_DIR)]
    if current_pythonpath:
        path_parts.append(current_pythonpath)
    return os.pathsep.join(path_parts)


def _run_case(
    case_name: str,
    fifo_depth: int,
    num_queues: int,
    max_burst_beats: int,
    cocotb_filter: str | None = None,
):
    new_pythonpath = _pythonpath()
    os.environ["PYTHONPATH"] = new_pythonpath

    sim = get_runner("questa")
    sim_args = [
        "-64",
        "-voptargs=+acc",
    ]

    rtl_parameters = {
        "FIFO_DEPTH": fifo_depth,
        "NUM_QUEUES": num_queues,
        "MAX_BURST_BEATS": max_burst_beats,
        "DESC_DEPTH": _env_int("TX_TB_DESC_DEPTH", 32),
    }
    parameter_env = {f"TX_TB_{key}": str(value) for key, value in rtl_parameters.items()}
    os.environ.update(parameter_env)

    build_dir = TX_TB_DIR / f"sim_build_fullchain_{case_name}"
    sim.build(
        sources=[str(source) for source in sources],
        hdl_toplevel="tx_top",
        build_dir=str(build_dir),
        parameters=rtl_parameters,
        always=True,
        clean=True,
    )

    waves = os.environ.get("COCOTB_WAVES", "1") != "0"
    extra_env = {
        "TOPLEVEL_LANG": "verilog",
        "PYTHONPATH": new_pythonpath,
        **parameter_env,
    }
    if cocotb_filter:
        extra_env["COCOTB_TEST_FILTER"] = cocotb_filter
    else:
        extra_env.pop("COCOTB_TEST_FILTER", None)
        os.environ.pop("COCOTB_TEST_FILTER", None)

    sim.test(
        hdl_toplevel="tx_top",
        test_module="TX.tb.tx_test",
        waves=waves,
        test_args=sim_args,
        extra_env=extra_env,
    )


@pytest.mark.parametrize(
    "case_name,fifo_depth,num_queues,max_burst_beats,cocotb_filter",
    [
        (
            "default",
            _env_int("TX_TB_FIFO_DEPTH", 64),
            _env_int("TX_TB_NUM_QUEUES", 4),
            _env_int("TX_TB_MAX_BURST_BEATS", 256),
            None,
        ),
        ("num_queues_2_smoke", 64, 2, 256, SMOKE_FILTER),
        ("num_queues_3_smoke", 64, 3, 256, SMOKE_FILTER),
        ("small_fifo_smoke", 4, 4, 256, SMOKE_FILTER),
        ("num_queues_1_smoke", 64, 1, 256, SMOKE_FILTER),
    ],
)
def test_tx_full_chain(case_name, fifo_depth, num_queues, max_burst_beats, cocotb_filter):
    _run_case(case_name, fifo_depth, num_queues, max_burst_beats, cocotb_filter)


if __name__ == "__main__":
    _run_case(
        "default",
        _env_int("TX_TB_FIFO_DEPTH", 64),
        _env_int("TX_TB_NUM_QUEUES", 4),
        _env_int("TX_TB_MAX_BURST_BEATS", 256),
    )
