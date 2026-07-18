import os
from PIL import Image, ImageDraw, ImageFilter
import random

assets_dir = "/home/sarthak/arova/frontend/src/assets"
os.makedirs(assets_dir, exist_ok=True)

# 1. Generate 512x512 mid-gray noise PNG
# Base color #808080
noise_img = Image.new("RGBA", (512, 512), (128, 128, 128, 255))
pixels = noise_img.load()

# We want very subtle fractal-like noise, or just uniform noise added/subtracted
for y in range(512):
    for x in range(512):
        # subtle noise +/- 12
        n = random.randint(-12, 12)
        v = 128 + n
        pixels[x, y] = (v, v, v, 255)

noise_img.save(os.path.join(assets_dir, "noise.png"))
print("Generated noise.png")

# 2. Generate 400x400 pre-blurred fog PNG
# We need a soft white circle fading to transparent
fog_img = Image.new("RGBA", (400, 400), (255, 255, 255, 0))
draw = ImageDraw.Draw(fog_img)

# Draw a white circle in the middle
draw.ellipse((100, 100, 300, 300), fill=(255, 255, 255, 255))

# Blur heavily to create a gradient (approx Gaussian blur radius 50)
fog_img = fog_img.filter(ImageFilter.GaussianBlur(radius=50))
fog_img.save(os.path.join(assets_dir, "fog.png"))
print("Generated fog.png")
