import os
import glob
import shutil
from cocotb_tools.runner import get_runner
from ethernet_assembler.tb.ethernet_assembler_sequence_item import EthernetAssemblerSequenceItem
from ethernet_assembler.tb.ethernet_assembler_transaction import (
    EthernetAssemblerTransaction,
)

rtl_utils = glob.glob("rtl_utils/*.sv")

sources = [
    "ethernet_assembler/rtl/nic_global_package.sv",
    "ethernet_assembler/rtl/ethernet_assembler.sv",
] + rtl_utils


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


def test_resize_module():
    base_dir = os.getcwd()

    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = base_dir + os.pathsep + current_pythonpath

    sim_name = _select_simulator()
    sim = get_runner(sim_name)

    rtl_parameters = {
        "DATA_IN_W": EthernetAssemblerSequenceItem.DATA_IN_W,
        "DATA_OUT_W": EthernetAssemblerTransaction.DATA_OUT_W,
    }

    sim_test_args = []
    if sim_name == "questa":
        sim_test_args = [
            "-voptargs=+acc",
        ]

    sim.build(
        sources=sources,
        hdl_toplevel="ethernet_assembler",
        build_dir="sim_build",
        parameters=rtl_parameters,
        #gui= True,
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="ethernet_assembler",
        test_module="ethernet_assembler.tb.ethernet_assembler_test",
        waves=True,
        test_args=sim_test_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )


if __name__ == "__main__":
    test_resize_module()
