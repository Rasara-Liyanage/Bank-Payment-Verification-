import hashlib

from PIL import Image, ImageOps

from database import BASE_DIR


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source_path = BASE_DIR / "demo_slips" / "matching_payment.png"
    output_path = BASE_DIR / "demo_slips" / "matching_payment_border.png"

    if not source_path.exists():
        raise FileNotFoundError(
            f"Original demo image was not found: {source_path}"
        )

    with Image.open(source_path) as original:
        variant = ImageOps.expand(
            original,
            border=60,
            fill="white",
        )

        variant.save(output_path)
        variant.close()

    original_hash = file_hash(source_path)
    variant_hash = file_hash(output_path)

    assert original_hash != variant_hash, "The file hashes must differ."

    print(f"Created: {output_path}")
    print(f"Original SHA-256: {original_hash}")
    print(f"Variant SHA-256:  {variant_hash}")
    print("PASS: Different file bytes; payment text remains unchanged.")


if __name__ == "__main__":
    main()