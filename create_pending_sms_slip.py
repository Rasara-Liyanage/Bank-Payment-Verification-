from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

from database import BASE_DIR


def main():
    sri_lanka_time = timezone(timedelta(hours=5, minutes=30))
    payment_date = datetime.now(sri_lanka_time).date().isoformat()

    output_dir = BASE_DIR / "demo_slips"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "pending_sms_payment.png"

    lines = [
        "DEMO ONLY - NOT A REAL PAYMENT",
        "Business: BuildStart Demo Store",
        "Bank: DEMO-BANK",
        "Amount: LKR 5000.00",
        "Receiving Account: 001234567890",
        "Transaction Reference: DEMO-TXN-003",
        "Order Reference: BST-DEMO-002",
        f"Payment Date: {payment_date}",
    ]

    with Image.new("RGB", (1600, 850), "white") as image:
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=42)
        draw.multiline_text(
            (60, 60), "\n".join(lines), fill="black", font=font, spacing=30
        )
        image.save(output_path)

    print(f"Created: {output_path}")
    print("Upload this slip for ORD-002.")
    print("Transaction reference: DEMO-TXN-003")
    print(f"Payment date: {payment_date}")
    print("SIMULATED TEST DATA - NOT A REAL PAYMENT.")


if __name__ == "__main__":
    main()
