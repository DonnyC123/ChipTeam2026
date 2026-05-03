import os
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RX_TB_ROOT = REPO_ROOT / "rx_tb"
RX_FIFO_ROOT = REPO_ROOT / "rx_fifo"

sources = [
    REPO_ROOT / "rtl_utils" / "if" / "axi_stream_if.sv",
    RX_FIFO_ROOT / "rtl" / "rx_fifo_pkg.sv",
    RX_FIFO_ROOT / "rtl" / "rx_async_fifo.sv",
    RX_FIFO_ROOT / "rtl" / "rx_fifo_ctrl.sv",
    REPO_ROOT / "alignment_finder" / "rtl" / "alignment_finder.sv",
    REPO_ROOT / "ethernet_assembler" / "rtl" / "nic_global_package.sv",
    REPO_ROOT / "ethernet_assembler" / "rtl" / "ethernet_assembler.sv",
    REPO_ROOT / "bubbler" / "rtl" / "bubbler.sv",
    REPO_ROOT / "descrambler" / "rtl" / "descrambler.sv",
    RX_TB_ROOT / "rtl" / "rx_top.sv",
    RX_TB_ROOT / "rtl" / "rx_top_wrapper.sv",
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
        "Set SIM to a supported cocotb runner name if needed."
    )


def test_rx_path():
    from cocotb_tools.runner import get_runner

    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = str(REPO_ROOT) + os.pathsep + current_pythonpath

    sim_name = _select_simulator()
    sim = get_runner(sim_name)

    sim_test_args = []
    if sim_name == "questa":
        sim_test_args = ["-voptargs=+acc", "-t", "ps"]

    sim.build(
        sources=[str(s) for s in sources],
        hdl_toplevel="rx_top_wrapper",
        build_dir=str(REPO_ROOT / "sim_build" / "rx_tb"),
        timescale=("1ns", "1ps"),
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="rx_top_wrapper",
        test_module="rx_tb.tb.rx_test",
        waves=True,
        test_args=sim_test_args,
        timescale=("1ns", "1ps"),
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )


if __name__ == "__main__":
    test_rx_path()
