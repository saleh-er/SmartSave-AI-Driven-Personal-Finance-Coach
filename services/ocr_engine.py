import pytesseract
from PIL import Image
import re
import io
import sys

# IMPORTANT FOR WINDOWS USERS: 
# If you get a TesseractNotFoundError, uncomment the line below and 
# update the path to your actual Tesseract installation folder.
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class OCREngine:
    @staticmethod
    def extract_data(image_bytes):
        try:
            # Open the image using Pillow
            img = Image.open(io.BytesIO(image_bytes))
            
            # Perform OCR with multi-language support (English + French)
            # Custom config added to treat the image as a single block of text
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(img, lang='eng+fra', config=custom_config)
            
            print("\n--- OCR RAW START ---")
            print(text) 
            print("--- OCR RAW END ---\n")

            # 1. Improved Amount Detection
            # Specifically looks for keywords like TOTAL, EUR, or AMOUNT
            amount = 0.0
            total_match = re.search(r'(?:TOTAL|AMOUNT|EUR|MONTANT)[:\s]*([\d+[.,]\d{2})', text, re.IGNORECASE)
            
            if total_match:
                amount = float(total_match.group(1).replace(',', '.'))
            else:
                # Fallback: Find all prices and take the highest one
                amounts = re.findall(r'\d+[.,]\d{2}', text)
                if amounts:
                    amount = max([float(a.replace(',', '.')) for a in amounts])

            # 2. Improved Merchant Extraction
            # We take the first meaningful line (avoiding weird characters)
            lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 2]
            merchant = lines[0] if lines else "Unknown Store"

            # 3. Simple Category Guessing
            # You can expand this list to make the AI smarter
            category = "Shopping"
            lowered_text = text.lower()
            if any(word in lowered_text for word in ["coffee", "restaurant", "food", "eat", "cafe"]):
                category = "Food"
            elif any(word in lowered_text for word in ["uber", "taxi", "train", "fuel", "gas"]):
                category = "Transport"
            elif any(word in lowered_text for word in ["netflix", "spotify", "disney", "prime"]):
                category = "Subs"

            return {
                "merchant": merchant,
                "amount": amount,
                "category": category
            }
        except Exception as e:
            print(f"!!! OCR ENGINE ERROR: {e}")
            return {
                "merchant": "Scan Error",
                "amount": 0.0,
                "category": "None"
            }