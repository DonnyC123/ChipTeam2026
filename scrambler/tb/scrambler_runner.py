import os
import glob
from cocotb_tools.runner import get_runner


rtl_utils = glob.glob("rtl_utils/*.sv")
sources = [
    *rtl_utils,
    "scrambler/rtl/scrambler.sv",
]

def test_scrambler():
    base_dir = os.getcwd()

    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = base_dir + os.pathsep + current_pythonpath

    sim = get_runner("questa")

    modelsim_sim_args = [
        "-voptargs=+acc",
    ]


    sim.build(
        sources=sources,
        hdl_toplevel="scrambler",    # Top-level module name
        build_dir="sim_build",
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="scrambler",  # Top-level module name
        test_module="scrambler.tb.scrambler_test",
        waves=True,
        test_args=modelsim_sim_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )

if __name__ == "__main__":
    test_scrambler()