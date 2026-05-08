import os
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

sources = [
    REPO_ROOT / "rtl_utils" / "data_pipeline.sv",
    REPO_ROOT / "ethernet_parser" / "rtl" / "parser_pkg.sv",
    REPO_ROOT / "ethernet_parser" / "rtl" / "ethernet_parser.sv",
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


def test_ethernet_parser():
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
        hdl_toplevel="ethernet_parser",
        build_dir=str(REPO_ROOT / "sim_build" / "ethernet_parser_tb"),
        timescale=("1ns", "1ps"),
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="ethernet_parser",
        test_module="ethernet_parser.tb.ethernet_parser_test",
        waves=True,
        test_args=sim_test_args,
        timescale=("1ns", "1ps"),
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )


if __name__ == "__main__":
    test_ethernet_parser()
