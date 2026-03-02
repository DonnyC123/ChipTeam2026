import os
import glob
from cocotb_tools.runner import get_runner
from median_filter.tb.median_filter_sequence_item import MedianFilterSequenceItem
from median_filter.tb.median_filter_out_transaction import (
    MedianFilterOutTransaction,
)

rtl_utils = glob.glob("rtl_utils/*.sv")

sources = [
    "median_filter/rtl/median_filter_pkg.sv",
    "median_filter/rtl/median_filter.sv",
    "median_filter/rtl/pixel_valid_if.sv",
] + rtl_utils


def test_resize_module():
    base_dir = os.getcwd()

    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = base_dir + os.pathsep + current_pythonpath

    sim = get_runner("questa")

    rtl_parameters = {
        "pixel_valid_if_i": MedianFilterSequenceItem.pixel_valid_if_i,
        "pixel_valid_if_o": MedianFilterOutTransaction.pixel_valid_if_o,
    }

    modelsim_sim_args = [
        "-voptargs=+acc",
    ]

    sim.build(
        sources=sources,
        hdl_toplevel="median_filter",
        build_dir="sim_build",
        parameters=rtl_parameters,
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="median_filter",
        test_module="median_filter.tb.median_filter_test",
        waves=True,
        test_args=modelsim_sim_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )


if __name__ == "__main__":
    test_resize_module()
