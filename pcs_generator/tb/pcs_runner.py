import glob
import os
import shutil

import pytest


rtl_utils = glob.glob("rtl_utils/*.sv")

sources = [
    "pcs_generator/rtl/pcs_pkg.sv",
    "pcs_generator/rtl/tx_axis_if.sv",
    "pcs_generator/rtl/data_pipeline.sv",
    "pcs_generator/rtl/pcs_generator.sv",
    "pcs_generator/rtl/pcs_generator_tb_top.sv",
] + rtl_utils


def _select_simulator() -> str:
    sim_env = os.environ.get("SIM")
    if sim_env:
        return sim_env

    if shutil.which("vsim") is not None:
        return "questa"

    if shutil.which("verilator") is not None:
        return "verilator"

    pytest.skip(
        "No supported simulator found in PATH (expected 'vsim' or 'verilator'). "
        "Set SIM to a supported cocotb runner name if needed."
    )


def test_pcs_generator():
    get_runner = pytest.importorskip("cocotb_tools.runner").get_runner

    base_dir = os.getcwd()
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = base_dir + os.pathsep + current_pythonpath

    sim_name = _select_simulator()
    sim = get_runner(sim_name)

    sim_test_args = []
    if sim_name == "questa":
        sim_test_args = [
            "-voptargs=+acc",
        ]

    sim.build(
        sources=sources,
        hdl_toplevel="pcs_generator_tb_top",
        build_dir="sim_build/pcs_generator",
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="pcs_generator_tb_top",
        test_module="pcs_generator.tb.pcs_generator_test",
        waves=True,
        gui=False,
        test_args=sim_test_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )


if __name__ == "__main__":
    test_pcs_generator()
