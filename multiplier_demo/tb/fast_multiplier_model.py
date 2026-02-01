from tb_utils.generic_model import GenericModel


class FastMultiplierModel(GenericModel):
    async def process_notification(self, notification):
        await self.expected_queue.put(notification)
