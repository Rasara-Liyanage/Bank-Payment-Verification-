import pytesseract
from PIL import Image, ImageDraw, ImageFont


pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def main():
    # Create a clear test image in memory.
    image = Image.new("RGB", (1200, 350), color="white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=40)

    sample_text = (
        "DEMO PAYMENT - NOT A REAL TRANSACTION\n"
        "Amount: LKR 5000.00\n"
        "Reference: BST-DEMO-001"
    )

    draw.multiline_text(
        (40, 40),
        sample_text,
        font=font,
        fill="black",
        spacing=20,
    )

    # Read the image using Tesseract.
    extracted_text = pytesseract.image_to_string(
        image,
        lang="eng",
        config="--psm 6",
        timeout=15,
    )

    print("OCR RESULT:")
    print(extracted_text.strip())


if __name__ == "__main__":
    main()