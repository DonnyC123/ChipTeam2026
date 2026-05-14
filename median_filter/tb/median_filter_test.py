import os
from typing import List, Tuple

import cocotb
from PIL import Image

from tb_utils.tb_common import initialize_tb
from median_filter.tb.median_filter_test_base import MedianFilterTestBase

from pathlib import Path

RGB = Tuple[int, int, int]


def load_rgb_image_rows(path: str) -> Tuple[int, int, List[List[RGB]]]:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    pix = list(im.getdata())
    rows = [pix[y * w : (y + 1) * w] for y in range(h)]
    return w, h, rows


@cocotb.test()

async def sanity_test(dut):
    await initialize_tb(dut, clk_period_ns=10)

    # Point this at whatever image you want to stream
    # You can also pass this via an env var from the runner.

    TB_DIR = Path(__file__).resolve().parent
    image_path = TB_DIR / "images" / "input.png"
    image_path = str(image_path)


    w, h, image_rows = load_rgb_image_rows(image_path)

    # round_half_up must match your RTL averaging behavior
    testbase = MedianFilterTestBase(
        dut,
        image_w=w,
        image_h=h,
        image_path=image_path,
        round_half_up=True,   # set False if RTL uses floor
    )

    # Stream the image pixels into the DUT (this also sends "start" to the model)
    await testbase.sequence.add_image_raster(image_rows)

    # Wait for all input transactions to be driven
    await testbase.wait_for_driver_done()

    # Scoreboard checks DUT outputs against model.expected_queue
    await testbase.scoreboard.check()
