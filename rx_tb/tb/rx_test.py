# rx_test.py
import cocotb
from cocotb.clock    import Clock
from cocotb.triggers import RisingEdge, ClockCycles

from tb_utils.generic_drivers       import GenericDriver
from tb_utils.abstract_transactions import AbstractTransaction
from tb_utils.generic_monitor       import GenericValidMonitor

from rx_tb.tb.rx_transaction    import RxTransaction
from rx_tb.tb.rx_sequence_item  import RxSequenceItem
from rx_tb.tb.rx_sequence       import RxSequence
from rx_tb.tb.rx_scoreboard     import RxScoreboard

CLK_PERIOD_NS = 10
RESET_CYCLES  = 5
LOCK_IDLES    = 64
FLUSH_CYCLES  = 900

class PayloadMonitor(GenericValidMonitor):
    async def _monitor(self):
        while True:
            await RisingEdge(self.dut.clk)

            txn = RxTransaction()
            txn.checksum_drop_o = self.dut.checksum_drop_o.value
            txn.parser_valid_o  = self.dut.parser_valid_o.value

            if txn.valid:
                self.actual_queue.put_nowait(txn)

async def init_dut(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())

    dut.raw_valid_i.value = 0
    dut.raw_data_i.value  = 0
    dut.rst.value         = 1
    await ClockCycles(dut.clk, RESET_CYCLES)
    dut.rst.value = 0
    await RisingEdge(dut.clk)

    driver     = GenericDriver(dut, RxSequenceItem)
    monitor    = PayloadMonitor(dut, RxTransaction)
    scoreboard = RxScoreboard()
    seq        = RxSequence(driver)

    return seq, monitor, scoreboard


async def drain_and_check(dut, monitor, scoreboard, cycles: int = FLUSH_CYCLES):
    await ClockCycles(dut.clk, cycles)
    await RisingEdge(dut.clk)

    while not monitor.actual_queue.empty():
        txn = monitor.actual_queue.get_nowait()
        scoreboard.ingest(txn)

    scoreboard.check_all_received()
    scoreboard.flush()
    # dut._log.info(scoreboard.summary())

@cocotb.test()
async def test_good_ipv4_ping_no_drop(dut):
    seq, monitor, scoreboard = await init_dut(dut)

    # Expect checksum checker NOT to drop
    scoreboard.add_expected(False)

    frame = [
        # -----------------------------------------------------------------
        # Ethernet Header
        # dst MAC
        0xDA, 0x02, 0x03, 0x04, 0x05, 0x06,

        # src MAC
        0x5A, 0x11, 0x12, 0x13, 0x14, 0x15,

        # EtherType = IPv4
        0x08, 0x00,

        # -----------------------------------------------------------------
        # IPv4 Header + ICMP payload
        0x45, 0x00, 0x00, 0x54,
        0x41, 0x2D, 0x40, 0x00,
        0x40, 0x01, 0xAF, 0x11,
        0xC0, 0xA8, 0x01, 0x05,
        0x08, 0x08, 0x08, 0x08,

        # ICMP
        0x08, 0x00, 0x4D, 0x56,
        0x00, 0x01, 0x00, 0x01,

        # payload
        0x61, 0x62, 0x63, 0x64,
        0x65, 0x66, 0x67, 0x68,
        0x69, 0x6A, 0x6B, 0x6C,
        0x6D, 0x6E, 0x6F, 0x70,
        0x71, 0x72, 0x73, 0x74,
        0x75, 0x76, 0x77, 0x61,
        0x62, 0x63, 0x64, 0x65,
        0x66, 0x67, 0x68, 0x69,
    ]

    await seq.send_idles(LOCK_IDLES)
    await seq.send_ethernet_frame(frame)
    await seq.send_idles(20)

    await drain_and_check(dut, monitor, scoreboard)

@cocotb.test()
async def test_bad(dut):
    seq, monitor, scoreboard = await init_dut(dut)

    scoreboard.add_expected(True)

    frame = [
        # -----------------------------------------------------------------
        # Ethernet Header
        # dst MAC
        0xDA, 0x02, 0x03, 0x04, 0x05, 0x06,

        # src MAC
        0x5A, 0x11, 0x12, 0x13, 0x14, 0x15,

        # EtherType = IPv4
        0x08, 0x00,

        # -----------------------------------------------------------------
        # IPv4 Header + ICMP payload
        0x45, 0x00, 0x00, 0x24,
        0x41, 0x2D, 0x40, 0x00,
        0x40, 0x01, 0xAF, 0x11,
        0xC0, 0xA8, 0x01, 0x05,
        0x08, 0x08, 0x08, 0x08,

        # ICMP
        0x08, 0x00, 0x4D, 0x56,
        0x00, 0x01, 0x00, 0x01,

        # payload
        0x61, 0x62, 0x63, 0x64,
        0x65, 0x66, 0x67, 0x68,
        0x69, 0x6A, 0x6B, 0x6C,
        0x6D, 0x6E, 0x6F, 0x70,
        0x71, 0x72, 0x73, 0x74,
        0x75, 0x76, 0x77, 0x61,
        0x62, 0x63, 0x64, 0x65,
        0x66, 0x67, 0x68, 0x69,
    ]

    await seq.send_idles(LOCK_IDLES)
    await seq.send_ethernet_frame(frame)
    await seq.send_idles(20)

    await drain_and_check(dut, monitor, scoreboard)

@cocotb.test()
async def test_bad(dut):
    seq, monitor, scoreboard = await init_dut(dut)

    scoreboard.add_expected(True)

    frame = [
        # -----------------------------------------------------------------
        # Ethernet Header
        # dst MAC
        0xDA, 0x02, 0x03, 0x04, 0x05, 0x06,

        # src MAC
        0x5A, 0x11, 0x12, 0x13, 0x14, 0x15,

        # EtherType = IPv4
        0x08, 0x00,

        # -----------------------------------------------------------------
        # IPv4 Header + ICMP payload
        0x45, 0x00, 0x00, 0x24,
        0x41, 0x2D, 0x40, 0x00,
        0x40, 0x01, 0xAF, 0x11,
        0xC0, 0xA8, 0x01, 0x05,
        0x08, 0x08, 0x08, 0x08,

        # ICMP
        0x08, 0x00, 0x4D, 0x56,
        0x00, 0x01, 0x00, 0x01,

        # payload
        0x61, 0x62, 0x63, 0x64,
        0x65, 0x66, 0x67, 0x68,
        0x69, 0x6A, 0x6B, 0x6C,
        0x6D, 0x6E, 0x6F, 0x70,
        0x71, 0x72, 0x73, 0x74,
        0x75, 0x76, 0x77, 0x61,
        0x62, 0x63, 0x64, 0x65,
        0x66, 0x67, 0x68, 0x69,
    ]

    await seq.send_idles(LOCK_IDLES)
    await seq.send_ethernet_frame(frame)

    for _ in range(100):
        await RisingEdge(dut.clk)
        dut._log.info(
            f"parser_state={dut.u_ethernet_parser.state_q.value} "
            f"out_valid={dut.out_valid_o.value} "
            f"bytes_valid={dut.bytes_valid_o.value} "
            f"payload_i={dut.u_ip_checksum.payload_i.value} "
            f"ipv4_i={dut.u_ip_checksum.ipv4_i.value} "
            f"ip_state={dut.u_ip_checksum.state_q.value}"
        )
        dut._log.info(
            f"ip_state={dut.u_ip_checksum.state_q.value} "
            f"acc={dut.u_ip_checksum.acc_q.value} "
            f"byte_cnt={dut.u_ip_checksum.byte_cnt_q.value} "
            f"ihl={dut.u_ip_checksum.ihl_bytes_q.value} "
            f"data={hex(dut.out_data_o.value)}"
        )

    await seq.send_idles(20)

    await drain_and_check(dut, monitor, scoreboard)