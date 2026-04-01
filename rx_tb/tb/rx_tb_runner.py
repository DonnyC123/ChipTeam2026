import os
import glob
from cocotb_tools.runner import get_runner

rtl_utils = glob.glob("rtl_utils/*.sv")

sources = [
    *rtl_utils,
    "alignment_finder/rtl/alignment_finder.sv",
    "ethernet_assembler/rtl/nic_global_package.sv",
    "ethernet_assembler/rtl/ethernet_assembler.sv",
    "bubbler/rtl/bubbler.sv",
    # descrambler here
    "rx_tb/rtl/rx_top.sv"
]

def test_rx_path():
    base_dir = os.getcwd()

    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = base_dir + os.pathsep + current_pythonpath

    sim = get_runner("questa")

    modelsim_sim_args = [
        "-voptargs=+acc",
    ]

    sim.build(
        sources=sources,
        hdl_toplevel="rx_top",    
        build_dir="sim_build",
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="rx_top",  
        test_module="rx_tb.tb.rx_test",
        waves=True,
        test_args=modelsim_sim_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
        },
    )

if __name__ == "__main__":
    test_rx_path()
