import os
import cocotb

from median_filter.tb.median_filter_test_base import MedianFilterTestBase
from tb_utils.tb_common import initialize_tb
from PIL import Image


def load_rgb_image(path: str):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    pix = list(im.getdata())
    img = [pix[y * w : (y + 1) * w] for y in range(h)]
    return img, w, h


@cocotb.test()
async def sanity_test(dut):
    await initialize_tb(dut, clk_period_ns=10)

    input_path = os.environ.get(
        "INPUT_IMG",
        "/home/lpi1150/ChipTeam2026/median_filter/tb/profile_test.jpg",
    )

    in_img, w, h = load_rgb_image(input_path)

    testbase = MedianFilterTestBase(
        dut,
        image_w=w,
        image_h=h,
        image_path=input_path,
    )

    await testbase.sequence.add_start_pulse()
    await testbase.sequence.add_image_raster(in_img)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()

    name, ext = os.path.splitext(input_path)
    out_path = f"{name}_filtered{ext}"
    testbase.scoreboard.model.save_output(out_path, fill_border_black=True)
