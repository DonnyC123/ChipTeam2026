from typing import List, Tuple, Optional
from PIL import Image
from tb_utils.generic_model import GenericModel

RGB = Tuple[int, int, int]

def load_rgb_image(path: str) -> Tuple[int, int, List[List[RGB]]]:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    pix = list(im.getdata())
    rows = [pix[y*w:(y+1)*w] for y in range(h)]
    return w, h, rows

def median4_avg(a: int, b: int, c: int, d: int, *, round_half_up: bool) -> int:
    s = sorted([a, b, c, d])
    mid_sum = s[1] + s[2]
    return (mid_sum + 1) // 2

def compute_median2x2_expected(img: List[List[RGB]], *, round_half_up: bool = True) -> List[RGB]:
    h = len(img)
    w = len(img[0])
    out: List[RGB] = []
    for y in range(1, h):
        for x in range(1, w):
            tl = img[y-1][x-1]
            tr = img[y-1][x]
            bl = img[y][x-1]
            br = img[y][x]
            out.append((
                median4_avg(tl[0], tr[0], bl[0], br[0], round_half_up=round_half_up),
                median4_avg(tl[1], tr[1], bl[1], br[1], round_half_up=round_half_up),
                median4_avg(tl[2], tr[2], bl[2], br[2], round_half_up=round_half_up),
            ))
    return out

class MedianFilterModel(GenericModel):
    def __init__(
        self,
        image_w: Optional[int] = None,
        image_h: Optional[int] = None,
        image_path: Optional[str] = None,
        *,
        round_half_up: bool = True,
    ):
        super().__init__()
        if image_path is None:
            raise ValueError("MedianFilterModel requires image_path")

        w, h, img = load_rgb_image(image_path)

        if image_w is not None and int(image_w) != w:
            raise ValueError(f"Image width mismatch: file {w}, expected {image_w}")
        if image_h is not None and int(image_h) != h:
            raise ValueError(f"Image height mismatch: file {h}, expected {image_h}")

        self.image_w = w
        self.image_h = h
        self.expected_pixels = compute_median2x2_expected(img, round_half_up=round_half_up)

        self._started = False

    async def _enqueue_expected(self):
        if self._started:
            return
        self._started = True
        for px in self.expected_pixels:
            await self.expected_queue.put(px)

    async def process_notification(self, notification):
        ev = notification.get("event")
        if ev == "start":
            self._started = False
            await self._enqueue_expected()
