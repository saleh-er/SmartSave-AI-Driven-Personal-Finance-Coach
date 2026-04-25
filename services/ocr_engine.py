import io
import os
import re

import pytesseract
from PIL import Image, ImageOps

# --- TESSERACT CONFIGURATION ---
TESSERACT_PATH = "/usr/bin/tesseract"

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    print(f"⚠️ WARNING: Tesseract executable not found at {TESSERACT_PATH}")


class OCREngine:
    @staticmethod
    def extract_data(image_bytes):
        try:
            # 1. Load image from bytes
            img = Image.open(io.BytesIO(image_bytes))

            # 2. Preprocessing for better accuracy
            img = ImageOps.grayscale(img)
            img = ImageOps.autocontrast(img)

            # 3. Extract raw text
            # lang='fra+eng+ara' supports French, English, and Arabic
            text = pytesseract.image_to_string(
                img,
                lang="fra+eng+ara",
                config="--psm 6"
            )

            lines = text.split("\n")
            scanned_items = []
            merchant = "Unknown Merchant"
            grand_total = 0.0

            print("\n--- STARTING ITEM-BY-ITEM SCAN ---")

            # 4. Extract merchant (usually first meaningful text line)
            for line in lines:
                clean_line = line.strip()
                if len(clean_line) > 2 and any(c.isalpha() for c in clean_line):
                    merchant = clean_line
                    break

            # 5. Extract line items (product name + price)
            for line in lines:
                clean_line = line.strip()
                price_search = re.search(r"(\d+[.,]\d{2})", clean_line)

                if price_search:
                    current_price = float(price_search.group(1).replace(",", "."))
                    product_name = clean_line.replace(price_search.group(0), "").strip()

                    # Ignore total/tax/cash lines to avoid duplicates
                    upper_line = clean_line.upper()
                    if any(key in upper_line for key in ["TOTAL", "SUBTOTAL", "TAX", "VAT", "CASH"]):
                        if "TOTAL" in upper_line and grand_total == 0:
                            grand_total = current_price
                        continue

                    if len(product_name) > 2:
                        scanned_items.append({
                            "label": product_name,
                            "price": current_price
                        })
                        print(f"Found Item: {product_name} -> {current_price}")

            # 6. Fallback for grand total
            if grand_total == 0:
                all_prices = re.findall(r"\d+[.,]\d{2}", text)
                if all_prices:
                    grand_total = max(float(p.replace(",", ".")) for p in all_prices)

            return {
                "merchant": merchant,
                "items": scanned_items,
                "total": grand_total,
                "category": "Shopping"
            }

        except Exception as e:
            print(f"❌ OCR Engine Error: {str(e)}")
            return {
                "merchant": "Scan Error",
                "items": [],
                "total": 0.0,
                "category": "None"
            }