import io
from pypdf import PdfReader

def extract_text_from_file(uploaded_file):
    """
    Extracts text from an uploaded file (PDF or TXT).
    Returns a tuple: (text, error_message)
    """
    if uploaded_file is None:
        return "", "No file provided."
    
    file_name = uploaded_file.name.lower()
    
    try:
        if file_name.endswith('.pdf'):
            reader = PdfReader(io.BytesIO(uploaded_file.read()))
            text_chunks = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_chunks.append(page_text.strip())
            
            extracted_text = "\n\n".join(text_chunks).strip()
            if not extracted_text:
                return "", "Could not extract text from this PDF. It may contain scanned images rather than selectable text."
            return extracted_text, None

        elif file_name.endswith('.txt'):
            content = uploaded_file.read()
            try:
                text = content.decode('utf-8')
            except UnicodeDecodeError:
                text = content.decode('latin-1', errors='ignore')
            return text.strip(), None

        else:
            return "", "Unsupported file type. Please upload a PDF or TXT file."

    except Exception as e:
        return "", f"Error reading file: {str(e)}"
