from tb_utils.generic_monitor import GenericValidMonitor

from rx_fifo.tb.rx_fifo_output_transaction import RXFifoCancelTransaction


class RXFifoCancelMonitor(GenericValidMonitor[RXFifoCancelTransaction]):
    def __init__(self, dut, output_transaction=RXFifoCancelTransaction):
        self.subscribers = []
        super().__init__(dut, output_transaction, clk=dut.s_clk)

    def add_subscriber(self, *subs):
        self.subscribers.extend(subs)

    async def monitor_loop(self):
        while True:
            transaction = await self.receive_transaction()
            for sub in self.subscribers:
                if hasattr(sub, "notify"):
                    await sub.notify(transaction.to_data)
