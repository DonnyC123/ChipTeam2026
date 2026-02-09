from tb_utils.generic_model import GenericModel


class FastMultiplierModel(GenericModel):
    async def process_notification(self, notification):
        output = notification["multiplier"] * notification["multiplicand"]
        await self.expected_queue.put(output)
