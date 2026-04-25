import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class CSVImporter:

    @staticmethod
    def parse_with_groq(content: str) -> list:
        prompt = f"""
You are a French bank statement parser (BNP Paribas, Societe Generale, CIC, Revolut, etc).

Analyze this bank statement content and extract ONLY debit transactions (money going OUT).
IGNORE all credit transactions (salaries, transfers received, deposits).

For each debit transaction return:
- merchant: clean readable name (max 30 chars)
- amount: positive float
- category: one of Food, Transport, Housing, Shopping, Health, Entertainment, Bills, Subs, Transfer, Other
- is_essential: true for Food/Housing/Health/Bills, false for others

Category rules:
- Food: INTERMARCHE, CARREFOUR, LIDL, PIZZA, restaurant, PRIMEURS, ALIM, DISTRIBUT, G.S.V
- Transport: RATP, SNCF, UBER, taxi, IMAGINE R, parking
- Housing: loyer, ALS VISALE, rent, EDF
- Bills: assurance, CARDIF, CPAM, CAISSE, OCTOPUS ENERGY, commissions bancaires, ESPRIT LIBRE
- Subs: NALA PAYMENTS, Netflix, Spotify, abonnement
- Transfer: VIREMENT, WERO, envoi argent
- Shopping: SUMUP, boutique, DIVINE BEAUTE, FRANCE RAMA, ROYAL M
- Other: frais divers

Return ONLY a valid JSON array, no explanation:
[{{"merchant": "name", "amount": 10.00, "category": "Food", "is_essential": true}}]

Bank statement content:
{content[:4000]}
"""
        try:
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000
            )
            raw = completion.choices[0].message.content.strip()
            raw = raw.replace('```json', '').replace('```', '').strip()
            transactions = json.loads(raw)
            return transactions
        except Exception as e:
            print(f"Groq parse error: {e}")
            return []

    @staticmethod
    def import_csv(file_content: bytes) -> list:
        try:
            try:
                text = file_content.decode('utf-8')
            except UnicodeDecodeError:
                text = file_content.decode('latin-1')
            return CSVImporter.parse_with_groq(text)
        except Exception as e:
            print(f"CSV import error: {e}")
            return []


class StatementImageParser:
    """Parse un relevé bancaire depuis une image via Groq vision."""

    @staticmethod
    def parse_image(image_bytes: bytes) -> list:
        import base64
        try:
            image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
            completion = groq_client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Analyze this bank statement image. Extract ONLY debit/expense transactions.
Return ONLY a valid JSON array:
[{"merchant": "name (max 30 chars)", "amount": 10.00, "category": "Food", "is_essential": true}]
Categories: Food, Transport, Housing, Shopping, Health, Entertainment, Bills, Subs, Transfer, Other
is_essential: true for Food/Housing/Health/Bills, false for others
No explanation, only JSON."""
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                            }
                        ]
                    }
                ],
                temperature=0.1,
                max_tokens=2000
            )
            raw = completion.choices[0].message.content.strip()
            raw = raw.replace('```json', '').replace('```', '').strip()
            return json.loads(raw)
        except Exception as e:
            print(f"Image parse error: {e}")
            return []


class PDFStatementParser:
    """Parse un relevé bancaire PDF via pypdf + Groq."""

    @staticmethod
    def parse_pdf(pdf_bytes: bytes) -> list:
        try:
            from pypdf import PdfReader
            from io import BytesIO

            reader = PdfReader(BytesIO(pdf_bytes))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"

            print(f"PDF text extracted: {len(text)} chars")
            print(f"Preview: {text[:300]}")

            if not text.strip():
                print("PDF text is empty")
                return []

            return CSVImporter.parse_with_groq(text)

        except Exception as e:
            print(f"PDF parse error: {e}")
            return []
