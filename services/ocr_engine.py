import pytesseract
from PIL import Image, ImageOps
import re
import io
import os

# --- TESSERACT CONFIGURATION ---
# Ensure Tesseract is installed at this path
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    print("⚠️ WARNING: Tesseract executable not found. Please check your installation path!")

class OCREngine:
    @staticmethod
    def extract_data(image_bytes):
        try:
            # 1. Load image from bytes
            img = Image.open(io.BytesIO(image_bytes))
            
            # 2. Preprocessing for better accuracy
            img = ImageOps.grayscale(img)
            img = ImageOps.autocontrast(img)
            
            # 3. Extracting raw text
            # lang='fra+eng+ara' supports French, English, and Arabic
            text = pytesseract.image_to_string(img, lang='fra+eng+ara', config='--psm 6')
            
            lines = text.split('\n')
            scanned_items = []
            merchant = "Unknown Merchant"
            grand_total = 0.0

            print("\n--- STARTING ITEM-BY-ITEM SCAN ---")

            # 4. Extract Merchant (usually the first line with letters)
            for line in lines:
                clean_line = line.strip()
                if len(clean_line) > 2 and any(c.isalpha() for c in clean_line):
                    merchant = clean_line
                    break

            # 5. Extract Line Items (Product Name + Price)
            for line in lines:
                clean_line = line.strip()
                # Pattern to find prices (e.g., 10.99 or 5,50)
                price_search = re.search(r'(\d+[.,]\d{2})', clean_line)
                
                if price_search:
                    current_price = float(price_search.group(1).replace(',', '.'))
                    # The product name is usually everything before the price
                    product_name = clean_line.replace(price_search.group(0), "").strip()
                    
                    # Ignore lines that are clearly 'Total' or 'Tax' to avoid duplicates
                    if any(key in clean_line.upper() for key in ["TOTAL", "SUBTOTAL", "TAX", "VAT", "CASH"]):
                        # If it's the Grand Total line, save it separately
                        if "TOTAL" in clean_line.upper() and grand_total == 0:
                            grand_total = current_price
                        continue
                    
                    if len(product_name) > 2:
                        scanned_items.append({
                            "label": product_name,
                            "price": current_price
                        })
                        print(f"Found Item: {product_name} -> {current_price}")

            # 6. Fallback for Grand Total
            if grand_total == 0:
                all_prices = re.findall(r'\d+[.,]\d{2}', text)
                if all_prices:
                    grand_total = max([float(p.replace(',', '.')) for p in all_prices])

            return {
                "merchant": merchant,
                "items": scanned_items,
                "total": grand_total,
                "category": "Shopping" # Default category
            }

        except Exception as e:
            print(f"❌ OCR Engine Error: {str(e)}")
            return {
                "merchant": "Scan Error",
                "items": [],
                "total": 0.0,
                "category": "None"
            }