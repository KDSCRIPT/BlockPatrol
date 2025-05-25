import re
import io
import json
import PyPDF2

def extract_text_from_pdf(pdf_content):
    """Extract text from PDF content."""
    text = ""
    pdf_file = io.BytesIO(pdf_content)
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        return ""

def extract_data(text):
    """Extract specific data using regex patterns."""
    data = {}
    
    # Extract FIR number
    fir_match = re.search(r'FIR No\.: (\d+/[A-Z]+/\d+)', text)
    if fir_match:
        data["FIR_no"] = fir_match.group(1)
    
    # Extract date
    date_match = re.search(r'Date of Incident: (\d{2} [A-Za-z]+ \d{4})', text)
    if date_match:
        # Convert date format
        date_str = date_match.group(1)
        try:
            from datetime import datetime
            parsed_date = datetime.strptime(date_str, "%d %B %Y")
            data["date"] = parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            data["date"] = date_str
    
    # Extract case type
    case_type_match = re.search(r'Sections: .*(Theft|Burglary|Robbery|House-breaking)', text, re.IGNORECASE)
    if case_type_match:
        data["case_type"] = case_type_match.group(1).lower()
    
    # Extract police handling
    police_match = re.search(r'(Inspector|SI|Officer) ([A-Za-z]+ [A-Za-z]+)', text)
    if police_match:
        data["police_handling"] = f"{police_match.group(1)} {police_match.group(2)}"
    
    return data

def get_raw_text(pdf_content):
    """Get the raw text from PDF without any specific data extraction."""
    try:
        text = extract_text_from_pdf(pdf_content)
        return {
            "success": True,
            "text": text
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def process_pdf(pdf_content):
    """Process a PDF file and extract data."""
    try:
        # Extract text from PDF
        text = extract_text_from_pdf(pdf_content)
        
        # Extract data using regex
        data = extract_data(text)
        
        return {
            "success": True,
            "extracted_data": data
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        } 