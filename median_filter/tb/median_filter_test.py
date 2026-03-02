import cocotb
from cocotb.triggers import RisingEdge, Timer

from median_filter.tb.median_filter_test_base import MedianFilterTestBase
from tb_utils.tb_common import initialize_tb

# Image size; must match RTL parameters in runner
IMAGE_LEN = 200
IMAGE_HEIGHT = 200


def _make_test_image():
    """Generate test image: list of (r, g, b) row by row."""
    pixels = []
    for row in range(IMAGE_HEIGHT):
        for col in range(IMAGE_LEN):
            r = (row * 16 + col) % 256
            g = (row * 16 + col + 1) % 256
            b = (row * 16 + col + 2) % 256
            pixels.append((r, g, b))
    return pixels


@cocotb.test()
async def median_filter_sanity_test(dut):
    await initialize_tb(dut, clk_period_ns=10)
    testbase = MedianFilterTestBase(dut, image_len=IMAGE_LEN, image_height=IMAGE_HEIGHT)

    await testbase.sequence.add_image_frame(
        IMAGE_LEN, IMAGE_HEIGHT, _make_test_image()
    )
    await testbase.wait_for_driver_done()

    # Wait for done_o so all outputs have been produced (allow enough cycles for 200x200)
    for _ in range(50000):
        await RisingEdge(dut.clk)
        if dut.done_o.value:
            break
    await Timer(100, unit="ns")

    await testbase.scoreboard.check()
