import os
import glob
import subprocess
from cocotb_tools.runner import get_runner

# RTL sources for median_filter (run from project root ChipTeam2026)
rtl_utils = glob.glob("rtl_utils/*.sv")
rtl_utils += glob.glob("rtl_utils/if/*.sv")

sources = [
    "median_filter/rtl/median_filter_pkg.sv",
    "median_filter/rtl/pixel_valid_if.sv",
    "median_filter/rtl/median_filter.sv",
    "median_filter/rtl/median_filter_top.sv",
] + rtl_utils

# Image size for test (must match median_filter_test.py)
IMAGE_LEN = 200
IMAGE_HEIGHT = 200


def test_median_filter():
    base_dir = os.getcwd()
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = base_dir + os.pathsep + current_pythonpath

    sim = get_runner("questa")

    rtl_parameters = {
        "IMAGE_LEN": IMAGE_LEN,
        "IMAGE_HEIGHT": IMAGE_HEIGHT,
    }

    modelsim_sim_args = [
        "-voptargs=+acc",
    ]

    sim.build(
        sources=sources,
        hdl_toplevel="median_filter_top",
        build_dir="median_filter/sim_build",
        parameters=rtl_parameters,
        always=True,
        clean=True,
    )

    # Set COCOTB_WAVES=0 or run without DISPLAY to disable GUI (e.g. SSH headless)
    waves = os.environ.get("COCOTB_WAVES", "1") != "0"
    sim.test(
        hdl_toplevel="median_filter_top",
        test_module="median_filter.tb.median_filter_test",
        waves=waves,
        test_args=modelsim_sim_args,
        extra_env={
            "TOPLEVEL_LANG": "systemverilog",
            "PYTHONPATH": new_pythonpath,
        },
    )

    # Auto-open waveform viewer when waves were enabled (vsim.wlf in build_dir)
    if waves:
        build_dir = os.path.abspath("median_filter/sim_build")
        wlf_path = os.path.join(build_dir, "vsim.wlf")
        if os.path.isfile(wlf_path):
            subprocess.Popen(
                ["vsim", "-view", wlf_path],
                cwd=build_dir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


if __name__ == "__main__":
    test_median_filter()
