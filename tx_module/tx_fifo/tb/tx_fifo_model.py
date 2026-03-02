from tb_utils.generic_model import GenericModel


class TxFifoModel(GenericModel):
    """Reference model for TX FIFO 256-to-64 bit width conversion.

    Each 256-bit DMA word produces 4 sequential 64-bit PCS beats:
        beat 0: data[ 63:  0], valid[ 7:0]
        beat 1: data[127: 64], valid[15:8]
        beat 2: data[191:128], valid[23:16]
        beat 3: data[255:192], valid[31:24]
    """

    BEATS_PER_WORD = 4
    PCS_DATA_W = 64
    PCS_VALID_W = 8

    async def process_notification(self, notification):
        data_256 = notification["data"]
        valid_32 = notification["valid"]

        mask_64 = (1 << self.PCS_DATA_W) - 1
        mask_8 = (1 << self.PCS_VALID_W) - 1

        for beat in range(self.BEATS_PER_WORD):
            pcs_data = (data_256 >> (beat * self.PCS_DATA_W)) & mask_64
            pcs_valid = (valid_32 >> (beat * self.PCS_VALID_W)) & mask_8
            await self.expected_queue.put((pcs_data, pcs_valid))
