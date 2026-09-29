from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

from database import BASE_DIR


DEMO_DIR = BASE_DIR / "demo_slips"
SRI_LANKA_TIME = timezone(timedelta(hours=5, minutes=30))


def create_slip(filename, amount, transaction_reference):
    payment_date = datetime.now(SRI_LANKA_TIME).date().isoformat()

    lines = [
        "DEMO ONLY - NOT A REAL PAYMENT",
        "Business: BuildStart Demo Store",
        "Bank: DEMO-BANK",
        f"Amount: LKR {amount}",
        "Receiving Account: 001234567890",
        f"Transaction Reference: {transaction_reference}",
        "Order Reference: BST-DEMO-001",
        f"Payment Date: {payment_date}",
    ]

    image = Image.new("RGB", (1600, 850), color="white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=42)

    draw.multiline_text(
        (60, 60),
        "\n".join(lines),
        font=font,
        fill="black",
        spacing=35,
    )

    output_path = DEMO_DIR / filename
    image.save(output_path)
    image.close()

    print(f"Created: {output_path}")


def main():
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    create_slip(
        "matching_payment.png",
        "5000.00",
        "DEMO-TXN-001",
    )

    create_slip(
        "wrong_amount.png",
        "4000.00",
        "DEMO-TXN-002",
    )


if __name__ == "__main__":
    main()