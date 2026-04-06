import os
import glob
import shutil
import pytest
from cocotb_tools.runner import get_runner
from multiplier_demo.tb.fast_multiplier_sequence_item import FastMultiplierSequenceItem
from multiplier_demo.tb.fast_multiplier_out_transaction import (
    FastMultiplierOutTransaction,
)

rtl_utils = glob.glob("rtl_utils/*.sv")

sources = [
    "multiplier_demo/rtl/multiplier_pkg.sv",
    "multiplier_demo/rtl/multiplier.sv",
    "multiplier_demo/rtl/fast_multiplier.sv",
] + rtl_utils


def _has_questa_license_hint() -> bool:
    license_env_vars = (
        "SALT_LICENSE_SERVER",
        "MGLS_LICENSE_FILE",
        "LM_LICENSE_FILE",
        "QUESTA_LICENSE_FILE",
    )
    return any(os.environ.get(var) for var in license_env_vars)


def _select_simulator() -> str:
    sim_env = os.environ.get("SIM")
    if sim_env:
        if sim_env.lower() == "questa" and not _has_questa_license_hint():
            pytest.skip(
                "SIM=questa requested, but no license environment is configured "
                "(set SALT_LICENSE_SERVER/MGLS_LICENSE_FILE/LM_LICENSE_FILE/QUESTA_LICENSE_FILE)."
            )
        return sim_env

    has_vsim = shutil.which("vsim") is not None
    has_verilator = shutil.which("verilator") is not None

    if has_vsim and _has_questa_license_hint():
        return "questa"

    if has_verilator:
        return "verilator"

    if has_vsim:
        pytest.skip(
            "Questa 'vsim' is available but no license environment is configured "
            "(set SALT_LICENSE_SERVER/MGLS_LICENSE_FILE/LM_LICENSE_FILE/QUESTA_LICENSE_FILE)."
        )

    pytest.skip("No supported simulator found in PATH (expected licensed 'vsim' or 'verilator').")


def test_resize_module():
    base_dir = os.getcwd()

    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = base_dir + os.pathsep + current_pythonpath

    sim_name = _select_simulator()
    sim = get_runner(sim_name)

    rtl_parameters = {
        "DIN_W": FastMultiplierSequenceItem.DIN_W,
        "DOUT_W": FastMultiplierOutTransaction.DOUT_W,
    }

    sim_test_args = []
    if sim_name == "questa":
        sim_test_args = [
            "-voptargs=+acc",
        ]

    sim.build(
        sources=sources,
        hdl_toplevel="fast_multiplier",
        build_dir="sim_build",
        parameters=rtl_parameters,
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="fast_multiplier",
        test_module="multiplier_demo.tb.fast_multiplier_test",
        waves=True,
        test_args=sim_test_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )


if __name__ == "__main__":
    test_resize_module()
