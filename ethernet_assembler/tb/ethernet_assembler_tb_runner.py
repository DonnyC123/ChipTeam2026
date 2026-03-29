import os
import glob
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


def test_resize_module():
    base_dir = os.getcwd()

    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = base_dir + os.pathsep + current_pythonpath

    sim = get_runner("questa")

    rtl_parameters = {
        "DATA_IN_W": EthernetAssemblerSequenceItem.DATA_IN_W,
        "DATA_OUT_W": EthernetAssemblerTransaction.DATA_OUT_W,
    }

    modelsim_sim_args = [
        "-voptargs=+acc",
    ]

    sim.build(
        sources=sources,
        hdl_toplevel="ethernet_assembler",
        build_dir="sim_build",
        parameters=rtl_parameters,
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="ethernet_assembler",
        test_module="ethernet_assembler.tb.ethernet_assembler_test",
        waves=True,
        test_args=modelsim_sim_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )


if __name__ == "__main__":
    test_resize_module()
