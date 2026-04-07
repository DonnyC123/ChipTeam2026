from tb_utils.generic_model import GenericModel


class TxSubsystemModel(GenericModel):
    PCS_DATA_W = 64
    PCS_VALID_W = 8
    BEATS_PER_WORD = 4

    async def process_notification(self, notification):
        if notification.get("op") != "axis_write":
            return

        data = int(notification.get("data", 0))
        keep = int(notification.get("keep", 0))
        last = int(notification.get("last", 0))

        data_mask = (1 << self.PCS_DATA_W) - 1
        keep_mask = (1 << self.PCS_VALID_W) - 1

        for beat in range(self.BEATS_PER_WORD):
            beat_data = (data >> (beat * self.PCS_DATA_W)) & data_mask
            beat_keep = (keep >> (beat * self.PCS_VALID_W)) & keep_mask
            beat_last = 1 if (last and beat == (self.BEATS_PER_WORD - 1)) else 0
            await self.expected_queue.put((beat_data, beat_keep, beat_last))
