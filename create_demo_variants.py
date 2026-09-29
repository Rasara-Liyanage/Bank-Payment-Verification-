"""Create synthetic unclear and suspicious-looking slips for the demo."""

from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from database import BASE_DIR


DEMO_DIR = BASE_DIR / "demo_slips"


def main():
    source = DEMO_DIR / "matching_payment.png"
    if not source.exists():
        raise FileNotFoundError("Run create_demo_slips.py first.")

    with Image.open(source) as original:
        tiny = original.resize((220, 115), Image.Resampling.BILINEAR)
        unclear = tiny.resize(original.size, Image.Resampling.NEAREST)
        unclear = unclear.filter(ImageFilter.GaussianBlur(radius=2.0))
        unclear.save(DEMO_DIR / "unclear_payment.png")
        unclear.close()
        tiny.close()

    day = datetime.now(
        timezone(timedelta(hours=5, minutes=30))
    ).date().isoformat()
    lines = [
        "DEMO ONLY - SYNTHETIC SUSPICIOUS SLIP",
        "Business: BuildStart Demo Store",
        "Bank: DEMO-BANK",
        "Amount: LKR 5000.00",
        "Receiving Account: 009999999999",
        "Transaction Reference: DEMO-TXN-SUSPECT",
        "Order Reference: BST-DEMO-001",
        f"Payment Date: {day}",
    ]
    image = Image.new("RGB", (1600, 850), "white")
    draw = ImageDraw.Draw(image)
    draw.multiline_text(
        (60, 60),
        "\n".join(lines),
        font=ImageFont.load_default(size=42),
        fill="black",
        spacing=35,
    )
    image.save(DEMO_DIR / "suspicious_wrong_account.png")
    image.close()
    print("Created unclear_payment.png and suspicious_wrong_account.png")


if __name__ == "__main__":
    main()
