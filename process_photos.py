"""Makes small web copies of the photos in photos-src/ and writes them to img/.
Strips camera metadata (including location), crops clutter, and blurs the
camera preview on the kiosk screen."""
import glob, os, sys
from PIL import Image, ImageOps

SRC, OUT, WIDTH = "photos-src", "img", 1100

def pick(*needles):
    for path in sorted(glob.glob(os.path.join(SRC, "*"))):
        name = os.path.basename(path)
        if all(n in name for n in needles):
            return path
    return None

def load(path):
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")

def save(im, name):
    if im.width > WIDTH:
        im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
    os.makedirs(OUT, exist_ok=True)
    im.save(os.path.join(OUT, name), "JPEG", quality=74, optimize=True, progressive=True)
    print(name, im.size, os.path.getsize(os.path.join(OUT, name)) // 1024, "KB")

def main():
    files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(SRC, "*")))
    room, kiosk = pick("_06"), pick("_05")
    lockers = next((os.path.join(SRC, f) for f in files
                    if "_06" not in f and "_05" not in f and f.lower().endswith((".jpg", ".jpeg", ".png"))), None)
    if room:
        save(load(room), "room.jpg")
    if lockers:
        im = load(lockers)
        save(im.crop((round(im.width * 0.29), round(im.height * 0.12), im.width, round(im.height * 0.78))), "lockers.jpg")
    if kiosk:
        im = load(kiosk)
        box = (round(im.width * 0.605), round(im.height * 0.365), round(im.width * 0.685), round(im.height * 0.415))
        patch = im.crop(box)
        patch = patch.resize((4, 3), Image.BILINEAR).resize(patch.size, Image.NEAREST)
        im.paste(patch, box)
        save(im, "kiosk.jpg")
    if not (room or lockers or kiosk):
        sys.exit("no photos found in photos-src/")

if __name__ == "__main__":
    main()
