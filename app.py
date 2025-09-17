from flask import Flask, request, jsonify, render_template
import os
import csv
from werkzeug.utils import secure_filename
from google import genai
from google.genai import types
import PyPDF2
import docx
import pdfplumber

# ----------------- CONFIG -----------------
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}
CONTACT_FILE = 'contacts.csv'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

GENIE_API_KEY = "AIzaSyDFUsoHH-PqOFnLMew4RtnpR7Ow7HBjt5o"  # Replace with your Gemini API Key
client = genai.Client(api_key=GENIE_API_KEY)

# ----------------- HELPER FUNCTIONS -----------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def summarize_text(text, language="English"):
    prompt = (
        f"Summarize the following legal text into structured sections with headings in {language}:\n"
        "1. Parties\n2. Purpose\n3. Rent & Deposit\n4. Responsibilities\n5. Termination\n6. Consequences\n"
        "Keep each point short and clear. Do not use asterisks or markdown."
        "\n\n" + text
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text


def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def extract_text_from_docx(file):
    text = ""
    doc = docx.Document(file)
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

# ----------------- ROUTES -----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/summarize", methods=["POST"])
def summarize_route():
    data = request.json
    text = data.get("text", "")
    if not text.strip():
        return jsonify({"error": "No text provided."})
    summary = summarize_text(text)
    return jsonify({"summary": summary})

@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded."})

    filename = file.filename.lower()
    try:
        if filename.endswith(".pdf"):
            text = extract_text_from_pdf(file)
        elif filename.endswith(".docx"):
            text = extract_text_from_docx(file)
        elif filename.endswith(".txt"):
            text = file.read().decode("utf-8")
        else:
            return jsonify({"error": "Unsupported file type."})

        summary = summarize_text(text)
        return jsonify({"summary": summary})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/contact", methods=["POST"])
def contact():
    data = request.json
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    message = data.get("message", "").strip()

    if not name or not email or not message:
        return jsonify({"error": "All fields are required."})

    try:
        file_exists = os.path.exists(CONTACT_FILE)
        with open(CONTACT_FILE, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            if not file_exists:
                writer.writerow(["Name", "Email", "Message"])
            writer.writerow([name, email, message])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/risks", methods=["POST"])
def detect_risks():
    data = request.json
    text = data.get("text", "")
    if not text.strip():
        return jsonify({"error": "No text provided."})

    prompt = (
        "Identify risky or unfavorable clauses in this legal text. "
        "Highlight financial liability, one-sided obligations, penalties, or vague terms. "
        "Return them as a list of risks with short explanations."
        "\n\n" + text
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return jsonify({"risks": response.text})

@app.route("/qa", methods=["POST"])
def legal_qa():
    data = request.json
    text = data.get("text", "")
    question = data.get("question", "")
    if not text.strip() or not question.strip():
        return jsonify({"error": "Text and question required."})

    prompt = (
        f"Based on this legal text, answer the question:\n"
        f"Question: {question}\n\n"
        f"Text:\n{text}\n\n"
        f"Give a clear, concise legal answer. Quote the relevant clause if possible."
    )
    response = client.models.generate_content(
        model="gemini-2.5-pro",  # use Pro here for deeper reasoning
        contents=prompt
    )
    return jsonify({"answer": response.text})

@app.route("/compare", methods=["POST"])
def compare_contracts():
    data = request.json
    text1 = data.get("text1", "")
    text2 = data.get("text2", "")
    if not text1.strip() or not text2.strip():
        return jsonify({"error": "Both texts required."})

    prompt = (
        "Compare these two contracts. Highlight differences in: Parties, Rent, Termination clauses, "
        "Responsibilities, and Liabilities. Show only key changes, not full text.\n\n"
        "Contract A:\n" + text1 + "\n\nContract B:\n" + text2
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return jsonify({"comparison": response.text})

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

@app.route("/download", methods=["POST"])
def download_summary():
    data = request.json
    summary = data.get("summary", "")
    filename = "summary_report.pdf"
    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    story = [Paragraph("Legal Summary", styles['Title']), Spacer(1, 12)]
    for line in summary.split("\n"):
        story.append(Paragraph(line, styles['Normal']))
        story.append(Spacer(1, 8))
    doc.build(story)
    return jsonify({"file": filename})


# ----------------- RUN -----------------
if __name__ == "__main__":
    app.run()
