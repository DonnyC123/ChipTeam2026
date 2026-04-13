from PIL import Image

from tb_utils.generic_model import GenericModel


class MedianFilterModel(GenericModel):
    async def process_notification(self, notification):
        img = notification
        width, height = img.size

        pixels = img.load()

        for y in range(height - 1):
            for x in range(width - 1):
                p1 = pixels[x, y]
                p2 = pixels[x + 1, y]
                p3 = pixels[x, y + 1]
                p4 = pixels[x + 1, y + 1]

                reds = [p1[0], p2[0], p3[0], p4[0]]
                greens = [p1[1], p2[1], p3[1], p4[1]]
                blues = [p1[2], p2[2], p3[2], p4[2]]

                reds.sort()
                greens.sort()
                blues.sort()

                med_r = (reds[1] + reds[2] + 1) // 2
                med_g = (greens[1] + greens[2] + 1) // 2
                med_b = (blues[1] + blues[2] + 1) // 2

                await self.expected_queue.put((med_r, med_g, med_b))
