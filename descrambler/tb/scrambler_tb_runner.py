import os
import glob
from cocotb_tools.runner import get_runner
from scrambler.tb.scrambler_sequence_item import MedianFilterSequenceItem
from scrambler.tb.scrambler_out_transaction import (
    MedianFilterOutTransaction,
)

rtl_utils = glob.glob("rtl_utils/*.sv")

sources = [
    "scrambler/rtl/scrambler.sv",
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
        hdl_toplevel="scrambler",
        build_dir="sim_build",
        parameters=rtl_parameters,
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="scrambler",
        test_module="scrambler.tb.scrambler_test",
        waves=True,
        test_args=modelsim_sim_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )


if __name__ == "__main__":
    test_resize_module()
