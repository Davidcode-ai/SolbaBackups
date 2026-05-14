from PIL import Image
import os

base_path = "src/frontend/assets/logo_solba.png"

if not os.path.exists(base_path):
    print("Logo not found!")
    exit(1)

img = Image.open(base_path)
if img.mode in ('RGBA', 'LA'):
    background = Image.new(img.mode[:-1], img.size, (255, 255, 255))
    background.paste(img, img.split()[-1])
    img = background

# Create ICO
img.save("src/frontend/assets/logo_solba.ico", format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])

# Create WizardImageFile (164x314)
img_large = img.resize((164, 314))
img_large.save("src/frontend/assets/logo_wizard.bmp", format="BMP")

# Create WizardSmallImageFile (55x55)
img_small = img.resize((55, 55))
img_small.save("src/frontend/assets/logo_wizard_small.bmp", format="BMP")

print("Images converted successfully!")
