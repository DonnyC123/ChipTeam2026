from cocotb import start_soon
from cocotb.queue import Queue
from cocotb.triggers import Event, RisingEdge


class TxAxisDriver:
    def __init__(self, dut, seq_item_type):
        self.dut = dut
        self.seq_item_type = seq_item_type
        self.seq_item_queue = Queue()
        self._active = False
        start_soon(self.driver_loop())

    async def send(self, transaction):
        done = Event()
        await self.seq_item_queue.put((transaction, done))
        await done.wait()

    async def add_idle(self, cycles=1):
        for _ in range(cycles):
            await self.send(self.seq_item_type.invalid_seq_item())

    async def busy(self):
        return self._active or not self.seq_item_queue.empty()

    async def wait_until_idle(self):
        while await self.busy():
            await RisingEdge(self.dut.dma_aclk)

    async def driver_loop(self):
        self._drive_invalid()
        while True:
            if self.seq_item_queue.empty():
                self._drive_invalid()
                await RisingEdge(self.dut.dma_aclk)
                continue

            transaction, done = await self.seq_item_queue.get()
            self._active = True
            if transaction.valid:
                while True:
                    self._drive_transaction(transaction)
                    await RisingEdge(self.dut.dma_aclk)
                    try:
                        accepted = bool(self.dut.s_axis_dma_tready_o.value)
                    except (TypeError, ValueError):
                        accepted = False
                    if accepted:
                        break
            else:
                self._drive_transaction(transaction)
                await RisingEdge(self.dut.dma_aclk)

            done.set()
            self._active = False

    def _drive_invalid(self):
        self._drive_transaction(self.seq_item_type.invalid_seq_item())

    def _drive_transaction(self, transaction):
        self.dut.s_axis_dma_tdata_i.value = transaction.s_axis_dma_tdata_i
        self.dut.s_axis_dma_tkeep_i.value = transaction.s_axis_dma_tkeep_i
        self.dut.s_axis_dma_tvalid_i.value = transaction.s_axis_dma_tvalid_i
        self.dut.s_axis_dma_tlast_i.value = transaction.s_axis_dma_tlast_i
