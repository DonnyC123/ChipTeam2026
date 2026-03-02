from tb_utils.generic_model import GenericModel


def _median_of_4(vals: list) -> int:
    """Median of 4 values: (sorted[1] + sorted[2] + 1) // 2 to match RTL rounding."""
    s = sorted(vals)
    return (s[1] + s[2] + 1) // 2


class MedianFilterModel(GenericModel):
    def __init__(self, image_len: int = 4, image_height: int = 4):
        super().__init__()
        self.image_len = image_len
        self.image_height = image_height
        self.num_received = 0
        self.line_buffer = [(0, 0, 0)] * image_len
        self.prev_col_pixel = (0, 0, 0)

    async def process_notification(self, notification):
        r, g, b = notification["pixel"]
        col = self.num_received % self.image_len
        row = self.num_received // self.image_len

        if row == 0:
            self.line_buffer[col] = (r, g, b)
        else:
            if col > 0:
                w = [
                    self.line_buffer[col - 1],
                    self.line_buffer[col],
                    self.prev_col_pixel,
                    (r, g, b),
                ]
                med_r = _median_of_4([x[0] for x in w])
                med_g = _median_of_4([x[1] for x in w])
                med_b = _median_of_4([x[2] for x in w])
                await self.expected_queue.put((med_r, med_g, med_b))
            self.line_buffer[col] = (r, g, b)
            self.prev_col_pixel = (r, g, b)

        self.num_received += 1
