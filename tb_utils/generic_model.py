from cocotb.queue import Queue


class GenericModel:
    def __init__(self):
        self.expected_queue = Queue()

    async def notify(self, notification):
        await self.process_notification(notification)

    async def process_notification(self, notification):
        await self.expected_queue.put(notification)

