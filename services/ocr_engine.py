import pytesseract
from PIL import Image, ImageOps
import re
import io
import os

# --- TESSERACT CONFIGURATION ---
# Path to the executable you just installed
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    print("⚠️ WARNING: Tesseract executable not found. Please check your installation path!")

class OCREngine:
    @staticmethod
    def extract_data(image_bytes):
        try:
            # 1. Load image from bytes sent by the browser
            img = Image.open(io.BytesIO(image_bytes))
            
            # 2. Image Optimization (Preprocessing)
            # Convert to grayscale and improve contrast to help the OCR
            img = ImageOps.grayscale(img)
            img = ImageOps.autocontrast(img)
            
            # 3. Text Extraction (OCR)
            # 'fra+eng+ara' allows reading French, English, and Arabic simultaneously
            # --psm 6 treats the image as a uniform block of text
            text = pytesseract.image_to_string(img, lang='fra+eng+ara', config='--psm 6')
            
            print("\n--- OCR RAW TEXT START ---")
            print(text) 
            print("--- OCR RAW TEXT END ---\n")

            # 4. Amount Extraction (Robust Regex)
            amount = 0.0
            # Look for keywords followed by a number (e.g., TOTAL 15.50)
            total_match = re.search(r'(?:TOTAL|AMOUNT|EUR|PAY|PRICE)[:\s]*(\d+[.,]\d{2})', text, re.IGNORECASE)
            
            if total_match:
                amount = float(total_match.group(1).replace(',', '.'))
            else:
                # Fallback: Find the highest number in the text
                amounts = re.findall(r'\d+[.,]\d{2}', text)
                if amounts:
                    amount = max([float(a.replace(',', '.')) for a in amounts])

            # 5. Merchant Extraction (Store Name)
            lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 2]
            # Take the first line containing letters (to avoid dates/numbers)
            merchant = "Unknown Merchant"
            for line in lines:
                if any(c.isalpha() for c in line):
                    merchant = line
                    break

            # 6. Smart Category Classification
            category = "Shopping"
            lowered_text = text.lower()
            
            # Keywords dictionary to guess the category
            keywords = {
                "Food": ["cafe", "starbucks", "resto", "mcdo", "bakery", "food", "eat", "grocery", "market"],
                "Transport": ["uber", "taxi", "train", "fuel", "shell", "gas", "parking"],
                "Subs": ["netflix", "spotify", "apple", "amazon", "prime", "disney"],
                "Housing": ["ikea", "rent", "hardware", "furniture"]
            }

            for cat, words in keywords.items():
                if any(word in lowered_text for word in words):
                    category = cat
                    break

            return {
                "merchant": merchant,
                "amount": amount,
                "category": category
            }

        except Exception as e:
            print(f"❌ OCR Engine Error: {str(e)}")
            return {
                "merchant": "Scan Error",
                "amount": 0.0,
                "category": "None"
            }