import cocotb
from ethernet_assembler.tb.ethernet_assembler_test_base import EthernetAssemblerTestBase
from tb_utils.tb_common import initialize_tb


@cocotb.test()
async def sanity_test(dut):
    await initialize_tb(dut, clk_period_ns=10)
    testbase = EthernetAssemblerTestBase(dut)
    # Start-of-frame control block (type 0x78).
    await testbase.sequence.add_control_block((0x78 << 56) | 0x01020304050607)
    # Data block 1 (in-frame payload).
    await testbase.sequence.add_data_block(0x1112131415161718)
    # Data block 2 (in-frame payload).
    await testbase.sequence.add_data_block(0x2122232425262728)
    # Data block 3 (in-frame payload).
    await testbase.sequence.add_data_block(0x3132333435363738)
    # Data block 4 (in-frame payload).
    await testbase.sequence.add_data_block(0x4142434445464748)
    # End-of-frame control block (type 0x87).
    await testbase.sequence.add_control_block((0x87 << 56) | 0x51525354555657)
    # Data block after end-of-frame (should be treated as out-of-frame data).
    await testbase.sequence.add_data_block(0x6162636465666768)
    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()
