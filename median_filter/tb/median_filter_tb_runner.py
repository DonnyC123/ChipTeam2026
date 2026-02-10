import os
import glob

from cocotb_tools.runner import get_runner
from PIL import Image

rtl_utils = glob.glob("rtl_utils/*.sv")

sources = [
    "median_filter/rtl/median_filter_pkg.sv",
    "median_filter/rtl/pixel_valid_if.sv",
    "median_filter/rtl/median_filter.sv",
    "median_filter/rtl/median_filter_tb_top.sv"
] + rtl_utils


def img_dims(path: str) -> tuple[int, int]:
    im = Image.open(path).convert("RGB")
    return im.size  


def test_median_filter():
    base_dir = os.getcwd()

    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = base_dir + os.pathsep + current_pythonpath

    sim = get_runner("questa")

    input_img = os.environ.get(
        "INPUT_IMG",
        "/home/lpi1150/ChipTeam2026/median_filter/tb/profile_test.jpg",
    )

    img_w, img_h = img_dims(input_img)

    rtl_parameters = {
        "IMAGE_LEN": img_w,
        "IMAGE_HEIGHT": img_h,
    }

    modelsim_sim_args = ["-voptargs=+acc"]

    sim.build(
        sources=sources,
        hdl_toplevel="median_filter_tb_top",
        build_dir="sim_build",
        parameters=rtl_parameters,
        always=True,
        clean=True,
    )

    sim.test(
        hdl_toplevel="median_filter_tb_top",
        test_module="median_filter.tb.median_filter_test",
        waves=True,
        test_args=modelsim_sim_args,
        extra_env={
            "TOPLEVEL_LANG": "verilog",
            "PYTHONPATH": new_pythonpath,
            "INPUT_IMG": input_img,
            "IMG_W": str(img_w),
            "IMG_H": str(img_h),
        },
    )


if __name__ == "__main__":
    test_median_filter()
