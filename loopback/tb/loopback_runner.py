"""pytest runner for the tx_cdc_top + wire_emulator + rx_top loopback test."""

import os
import shutil
from pathlib import Path

REPO_ROOT     = Path(__file__).resolve().parents[2]
LOOPBACK_ROOT = REPO_ROOT / "loopback"
TX_DIR        = REPO_ROOT / "TX"
RX_TB_ROOT    = REPO_ROOT / "rx_tb"
RX_FIFO_ROOT  = REPO_ROOT / "rx_fifo"
PCS_DIR       = TX_DIR / "rtl" / "pcs_generator"


def _pcs_sources() -> list[Path]:
    explicit_first = [
        PCS_DIR / "tx_axis_if.sv",
        PCS_DIR / "pcs_pkg.sv",
        PCS_DIR / "data_pipeline.sv",
    ]
    excluded = {p.name for p in explicit_first} | {"pcs_generator_tb_top.sv"}
    remaining = sorted(p for p in PCS_DIR.glob("*.sv") if p.name not in excluded)
    return [p for p in explicit_first if p.exists()] + remaining


sources = [
    REPO_ROOT / "rtl_utils" / "if" / "axi_stream_if.sv",
    REPO_ROOT / "rtl_utils" / "data_pipeline.sv",

    # TX side
    TX_DIR / "rtl" / "tx_fifo" / "tx_subsystem_pkg.sv",
    TX_DIR / "rtl" / "tx_fifo" / "tx_async_fifo.sv",
    TX_DIR / "rtl" / "tx_fifo" / "tx_subsystem.sv",
    *_pcs_sources(),
    TX_DIR / "rtl" / "scrambler" / "scrambler.sv",
    TX_DIR / "rtl" / "debubbler" / "debubbler.sv",
    TX_DIR / "tb" / "tx_cdc_top.sv",

    # RX side
    RX_FIFO_ROOT / "rtl" / "rx_fifo_pkg.sv",
    RX_FIFO_ROOT / "rtl" / "rx_async_fifo.sv",
    RX_FIFO_ROOT / "rtl" / "rx_fifo_ctrl.sv",
    REPO_ROOT / "alignment_finder" / "rtl" / "alignment_finder.sv",
    REPO_ROOT / "ethernet_assembler" / "rtl" / "nic_global_package.sv",
    REPO_ROOT / "ethernet_assembler" / "rtl" / "ethernet_assembler.sv",
    REPO_ROOT / "bubbler" / "rtl" / "bubbler.sv",
    REPO_ROOT / "descrambler" / "rtl" / "descrambler.sv",
    RX_TB_ROOT / "rtl" / "rx_top.sv",

    # Loopback glue
    LOOPBACK_ROOT / "rtl" / "wire_emulator.sv",
    LOOPBACK_ROOT / "tb"  / "loopback_top.sv",
]


def _select_simulator() -> str:
    sim_env = os.environ.get("SIM")
    if sim_env:
        return sim_env
    if shutil.which("vsim") is not None:
        return "questa"
    if shutil.which("verilator") is not None:
        return "verilator"
    raise SystemExit(
        "ERROR: No supported simulator found in PATH (expected 'vsim' or 'verilator'). "
        "Set SIM to override."
    )


def test_loopback():
    from cocotb_tools.runner import get_runner

    sim_name = _select_simulator()
    sim = get_runner(sim_name)

    pythonpath = str(REPO_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = pythonpath

    parameters = {
        "OFFSET_BITS": int(os.environ.get("LB_OFFSET_BITS", 17)),
        "FIFO_DEPTH":  int(os.environ.get("LB_FIFO_DEPTH", 64)),
        "DESC_DEPTH":  int(os.environ.get("LB_DESC_DEPTH", 32)),
        "NUM_QUEUES":  int(os.environ.get("LB_NUM_QUEUES", 4)),
    }

    sim_test_args = ["-voptargs=+acc", "-t", "ps"] if sim_name == "questa" else []

    sim.build(
        sources=[str(s) for s in sources],
        hdl_toplevel="loopback_top",
        build_dir=str(REPO_ROOT / "sim_build" / "loopback"),
        parameters=parameters,
        timescale=("1ns", "1ps"),
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="loopback_top",
        test_module="loopback.tb.loopback_test",
        waves=True,
        test_args=sim_test_args,
        timescale=("1ns", "1ps"),
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": pythonpath,
        },
    )


if __name__ == "__main__":
    test_loopback()
