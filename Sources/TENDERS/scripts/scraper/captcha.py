import cv2
import numpy as np
import easyocr
import re
import os

current_directory = os.getcwd()
print(f"Current working directory: {current_directory}")
def keep_large_regions(
    binary_img,
    min_area: int = 70
):
    inv = 255 - binary_img

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=8)

    h, w = binary_img.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)  # RGBA

    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            mask = labels == i
            rgba[mask] = (0, 0, 0, 255)  # black, opaque

    return rgba

def captcha_ocr():
    img = cv2.imread(rf"{current_directory}\captcha_image.png", cv2.IMREAD_GRAYSCALE)

    # Convert to binary 
    _, img = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY)
    rgba = keep_large_regions(img, min_area=75)

    # set transparent areas to white

    rgb = rgba[:, :, :3]
    alpha = rgba[:, :, 3] / 255.0

    white_bg = np.ones_like(rgb, dtype=np.uint8) * 255
    out = (rgb * alpha[..., None] + white_bg * (1 - alpha[..., None])).astype(np.uint8)

    cv2.imwrite(rf"{current_directory}\Sources\TENDERS\scripts\scraper\ocr_ready.png", out) 

    # "en" for English
    reader = easyocr.Reader(['en'])

    image_path = rf"{current_directory}\Sources\TENDERS\scripts\scraper\ocr_ready.png"

    image = cv2.imread(image_path)

    # Perform OCR
    result = reader.readtext(image)

    #remove any non alphanumeric characters
    text = "".join(re.sub(r"[^A-Za-z0-9]", "", d[1])
        for d in result
    )
    print(f"OCR Result: {text}")

    return text



