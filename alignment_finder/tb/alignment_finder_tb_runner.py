import os
import glob
from cocotb_tools.runner import get_runner

# If you have shared SV helpers
rtl_utils = glob.glob("rtl_utils/*.sv")

sources = [
    *rtl_utils,
    "alignment_finder/rtl/alignment_finder.sv",
]

def test_alignment_finder():
    base_dir = os.getcwd()

    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = base_dir + os.pathsep + current_pythonpath

    sim = get_runner("questa")

    rtl_parameters = {
        "DATA_WIDTH": 66,
        "GOOD_COUNT": 32,
        "BAD_COUNT": 8,
    }

    modelsim_sim_args = [
        "-voptargs=+acc",
    ]

    sim.build(
        sources=sources,
        hdl_toplevel="alignment_finder",    
        build_dir="sim_build_alignment",
        parameters=rtl_parameters,
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="alignment_finder",  
        test_module="alignment_finder.tb.alignment_finder_test",
        waves=True,
        test_args=modelsim_sim_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )

if __name__ == "__main__":
    test_alignment_finder()
