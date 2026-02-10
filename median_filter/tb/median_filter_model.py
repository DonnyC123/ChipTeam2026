from typing import List, Tuple
from tb_utils.generic_model import GenericModel
from PIL import Image
import os


def load_rgb_image(path: str) -> List[List[Tuple[int, int, int]]]:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    pix = list(im.getdata())
    return [pix[y*w:(y+1)*w] for y in range(h)]


def median4(a: int, b: int, c: int, d: int) -> int:
    s = sorted([a, b, c, d])
    return int((s[1] + s[2] + 1) / 2)


class MedianFilterModel(GenericModel):
    def __init__(self, image_w: int, image_h: int, image_path: str):
        super().__init__()
        self.image_w = int(image_w)
        self.image_h = int(image_h)

        self.img = load_rgb_image(image_path)
        if len(self.img) != self.image_h or len(self.img[0]) != self.image_w:
            raise ValueError(
                f"Image dims mismatch: got {len(self.img[0])}x{len(self.img)}, "
                f"expected {self.image_w}x{self.image_h}"
            )

        self.row = 0
        self.col = 0
        self.out_pixels: List[Tuple[int, int, int]] = []

    def _reset_stream_state(self):
        self.row = 0
        self.col = 0
        self.out_pixels = []  

    def save_output(self, out_path: str, fill_border_black: bool = True):
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

        w, h = self.image_w, self.image_h
        expected_n = (w - 1) * (h - 1)
        if len(self.out_pixels) != expected_n:
            raise RuntimeError(f"Expected {expected_n} output pixels, got {len(self.out_pixels)}")

        if fill_border_black:
            data = [(0, 0, 0)] * (w * h)
            k = 0
            for y in range(h):
                for x in range(w):
                    if y > 0 and x > 0:
                        data[y * w + x] = tuple(map(int, self.out_pixels[k]))
                        k += 1
            im = Image.new("RGB", (w, h))
            im.putdata(data)
        else:
            im = Image.new("RGB", (w - 1, h - 1))
            im.putdata([tuple(map(int, p)) for p in self.out_pixels])

        im.save(out_path)

    async def process_notification(self, notification):
        ev = notification.get("event")

        if ev == "start":
            self._reset_stream_state()
            return
        if ev != "pixel":
            return

        if self.row > 0 and self.col > 0:
            tl = self.img[self.row - 1][self.col - 1]
            tr = self.img[self.row - 1][self.col]
            bl = self.img[self.row][self.col - 1]
            br = self.img[self.row][self.col]

            PASSTHROUGH = False

            if PASSTHROUGH:
                exp = (br[0], br[1], br[2])
            else:
                exp = (
                    median4(tl[0], tr[0], bl[0], br[0]),
                    median4(tl[1], tr[1], bl[1], br[1]),
                    median4(tl[2], tr[2], bl[2], br[2]),
                )

         
            self.out_pixels.append(exp)

            await self.expected_queue.put(exp)

        self.row += (self.col + 1) // self.image_w
        self.col = (self.col + 1) % self.image_w
        


