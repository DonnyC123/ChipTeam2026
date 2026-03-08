import cocotb
from cocotb.triggers import RisingEdge, Timer
from tb_utils.tb_common import initialize_tb


def make_66b_block(header2: int, payload64: int = 0) -> int:
    header2 &= 0b11
    payload64 &= (1 << 64) - 1
    return (header2 << 64) | payload64


async def drive_word(dut, word: int, valid: int = 1):
    dut.data_valid_i.value = valid
    dut.data_i.value = word
    await RisingEdge(dut.clk)


async def drive_bubbles(dut, cycles: int):
    for _ in range(cycles):
        dut.data_valid_i.value = 0
        dut.data_i.value = 0
        await RisingEdge(dut.clk)


@cocotb.test()
async def lock_eventually_goes_high(dut):
    await initialize_tb(dut, clk_period_ns=10)

    good_count = int(getattr(dut, "GOOD_COUNT", 32))

    # Start clean
    dut.data_valid_i.value = 0
    dut.data_i.value = 0
    await Timer(1, units="ns")
    await drive_bubbles(dut, 2)

    bad0 = make_66b_block(0b00, 0)
    bad1 = make_66b_block(0b11, 0)
    await drive_word(dut, bad0, 1)
    await drive_word(dut, bad1, 1)

    good_word = make_66b_block(0b10, 0)

    saw_lock = False

    for i in range(good_count + 10):
        await drive_word(dut, good_word, 1)

        if int(dut.locked_o.value) == 1:
            dut._log.info(f"locked_o went high after {i+1} good words")
            saw_lock = True
            break

    assert saw_lock, (
        f"locked_o never went high after feeding {good_count + 10} "
        f"valid good-header blocks"
    )

    for _ in range(5):
        await drive_word(dut, good_word, 1)
        assert int(dut.locked_o.value) == 1, "locked_o dropped unexpectedly after lock"