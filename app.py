import os
import json
import uuid
from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import google.generativeai as genai
from PyPDF2 import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import threading
import time

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("\nWARNING: GEMINI_API_KEY not found in .env file.")
    print("Please set your Gemini API key in the .env file.\n")

genai.configure(api_key=GEMINI_API_KEY)

# Check for poppler-utils
try:
    from pdf2image import pdfinfo_from_path
    # Test if poppler is installed
    pdfinfo_from_path("test.pdf", poppler_path=None, userpw=None)
except Exception as e:
    if "poppler" in str(e).lower():
        print("\nWARNING: poppler-utils is not installed or not in PATH.")
        print("Please install poppler-utils:")
        print("- Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases/")
        print("- Linux: sudo apt-get install poppler-utils")
        print("- macOS: brew install poppler\n")
    else:
        # This is expected since test.pdf doesn't exist
        pass

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# Register Vazir font for Persian text
try:
    pdfmetrics.registerFont(TTFont('Vazir', 'static/fonts/Vazir.ttf'))
except:
    print("Warning: Vazir font not found. Using default font instead.")

# Dictionary to store translation progress
translation_jobs = {}

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    reader = PdfReader(pdf_path)
    text_by_pages = []
    
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text()
        if text.strip():  # Only add non-empty pages
            text_by_pages.append({
                'page_num': page_num + 1,
                'text': text
            })
    
    return text_by_pages, len(reader.pages)

def create_page_groups(pages, group_size=10):
    """Group pages into chunks of specified size"""
    return [pages[i:i + group_size] for i in range(0, len(pages), group_size)]

def translate_text(text, job_id, chunk_index, total_chunks, max_retries=3, retry_delay=5):
    """Translate text using Gemini API with retry mechanism"""
    retries = 0
    while retries <= max_retries:
        try:
            # Update status to show retry attempt if applicable
            if retries > 0:
                translation_jobs[job_id]['chunks'][chunk_index]['status'] = f'retrying ({retries}/{max_retries})'
                translation_jobs[job_id]['chunks'][chunk_index]['error'] = f'Retrying after rate limit error (attempt {retries}/{max_retries})'
            
            model = genai.GenerativeModel('gemini-2.0-flash')
            prompt = f"""تو یک مترجم حرفه‌ای و متخصص در ترجمه‌ی کتاب‌های انگلیسی به فارسی هستی. 
ترجمه‌های تو دقیق، روان، آکادمیک و مطابق با سبک نگارشی کتاب‌های چاپی و رسمی فارسی هستند. 
لطفاً تمام جملات متن را بدون حذف یا خلاصه‌سازی ترجمه کن و اطمینان حاصل کن که مفهوم، لحن، و سبک نویسنده در ترجمه حفظ شود.
ساختار پاراگراف‌ها و انسجام متن را دقیقاً مطابق با متن اصلی نگه‌دار.
اگر با اصطلاحات خاص یا فنی مواجه شدی، معادل دقیق و رایج فارسی آن‌ها را استفاده کن.
هدف، تولید ترجمه‌ای است که گویی متن در اصل به فارسی نوشته شده، نه صرفاً برگردان واژه‌به‌واژه.
 
متن برای ترجمه:
{text}"""
            
            response = model.generate_content(prompt)
            translated_text = response.text
            
            # Update job progress
            translation_jobs[job_id]['chunks'][chunk_index]['status'] = 'completed'
            translation_jobs[job_id]['chunks'][chunk_index]['translated_text'] = translated_text
            translation_jobs[job_id]['completed_chunks'] += 1
            
            # Calculate overall progress
            progress = (translation_jobs[job_id]['completed_chunks'] / total_chunks) * 100
            translation_jobs[job_id]['progress'] = progress
            
            if translation_jobs[job_id]['completed_chunks'] == total_chunks:
                translation_jobs[job_id]['status'] = 'completed'
                # Generate PDF when all chunks are translated
                generate_pdf(job_id)
            
            # Success - exit retry loop
            return
                
        except Exception as e:
            error_message = str(e)
            translation_jobs[job_id]['chunks'][chunk_index]['status'] = 'error'
            translation_jobs[job_id]['chunks'][chunk_index]['error'] = error_message
            
            # Check if it's a rate limit error
            if "quota" in error_message.lower() or "rate limit" in error_message.lower() or "429" in error_message:
                if retries < max_retries:
                    retries += 1
                    # Exponential backoff: wait longer with each retry
                    wait_time = retry_delay * (2 ** (retries - 1))
                    print(f"Rate limit hit for job {job_id}, chunk {chunk_index}. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    error_message = f"Rate limit exceeded after {max_retries} retries: {error_message}"
            
            # Update job with error information
            translation_jobs[job_id]['chunks'][chunk_index]['status'] = 'failed'
            translation_jobs[job_id]['chunks'][chunk_index]['error'] = error_message
            
            # Only mark the whole job as failed if it's not a rate limit error or we've exhausted retries
            if "quota" not in error_message.lower() and "rate limit" not in error_message.lower() and "429" not in error_message:
                translation_jobs[job_id]['status'] = 'failed'
            
            # Exit retry loop on non-rate-limit errors
            break

def generate_pdf(job_id):
    """Generate PDF from translated text"""
    try:
        job = translation_jobs[job_id]
        output_pdf_path = os.path.join(OUTPUT_FOLDER, f"{job_id}_translated.pdf")
        
        # Create PDF
        c = canvas.Canvas(output_pdf_path, pagesize=letter)
        width, height = letter
        
        # Set font for Persian text
        try:
            c.setFont('Vazir', 12)
        except:
            c.setFont('Helvetica', 12)
        
        # Combine all translated chunks in order
        all_pages = []
        for chunk in job['chunks']:
            if chunk['status'] == 'completed':
                all_pages.extend(chunk['pages'])
        
        # Sort pages by page number
        all_pages.sort(key=lambda x: x['page_num'])
        
        for i, page_info in enumerate(all_pages):
            if i > 0:
                c.showPage()  # Start a new page
                try:
                    c.setFont('Vazir', 12)
                except:
                    c.setFont('Helvetica', 12)
            
            # Add page number
            c.drawString(width - 100, height - 30, f"صفحه {page_info['page_num']}")
            
            # Get translated text for this page
            page_index = page_info['chunk_index']
            page_position = page_info['position_in_chunk']
            translated_text = job['chunks'][page_index]['translated_text']
            
            # Split text into lines and draw on PDF
            y_position = height - 50
            lines = translated_text.split('\n')
            for line in lines:
                if y_position < 50:  # Check if we need a new page
                    c.showPage()
                    try:
                        c.setFont('Vazir', 12)
                    except:
                        c.setFont('Helvetica', 12)
                    y_position = height - 50
                
                # Draw text right-to-left for Persian
                c.drawRightString(width - 50, y_position, line)
                y_position -= 15
        
        c.save()
        job['pdf_path'] = output_pdf_path
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        translation_jobs[job_id]['status'] = 'failed'
        translation_jobs[job_id]['error'] = f"Error generating PDF: {e}"

def process_pdf(file_path, job_id, pages_per_chunk=5):
    """Process PDF file for translation with rate limit management"""
    try:
        # Extract text from PDF
        pages, total_pages = extract_text_from_pdf(file_path)
        
        # Group pages into chunks based on user preference
        page_groups = create_page_groups(pages, pages_per_chunk)
        total_chunks = len(page_groups)
        
        # Initialize job structure
        translation_jobs[job_id] = {
            'file_path': file_path,
            'total_pages': total_pages,
            'status': 'in_progress',
            'progress': 0,
            'completed_chunks': 0,
            'chunks': [],
            'start_time': time.time()
        }
        
        # Process each chunk with controlled rate
        active_threads = []
        max_concurrent_threads = 2  # Limit concurrent API calls
        
        for chunk_index, page_group in enumerate(page_groups):
            # Prepare chunk data
            chunk_text = "\n\n=== PAGE BREAK ===\n\n".join([page['text'] for page in page_group])
            
            # Add page metadata to each page
            for i, page in enumerate(page_group):
                page['chunk_index'] = chunk_index
                page['position_in_chunk'] = i
            
            # Add chunk to job
            translation_jobs[job_id]['chunks'].append({
                'chunk_index': chunk_index,
                'pages': page_group,
                'original_text': chunk_text,
                'status': 'pending',
                'translated_text': ''
            })
            
            # Control the number of active threads to prevent rate limiting
            while len(active_threads) >= max_concurrent_threads:
                # Clean up finished threads
                active_threads = [t for t in active_threads if t.is_alive()]
                if len(active_threads) >= max_concurrent_threads:
                    # Wait before checking again
                    time.sleep(2)
            
            # Start translation in a separate thread with retry mechanism
            thread = threading.Thread(
                target=translate_text,
                args=(chunk_text, job_id, chunk_index, total_chunks, 3, 5)  # Added retry parameters
            )
            thread.daemon = True
            thread.start()
            active_threads.append(thread)
            
            # Larger delay between starting threads to prevent API rate limiting
            time.sleep(4)  # Increased from 1 to 4 seconds
            
    except Exception as e:
        translation_jobs[job_id] = {
            'status': 'failed',
            'error': str(e),
            'start_time': time.time(),
            'progress': 0,
            'total_pages': 0,
            'completed_chunks': 0,
            'chunks': []
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are allowed'}), 400
    
    # Get API key from request
    api_key = request.form.get('api_key')
    if not api_key:
        return jsonify({'error': 'API key is required'}), 400
    
    # Configure Gemini API with the provided key
    genai.configure(api_key=api_key)
    
    # Get pages per chunk from request (default to 5 if not provided)
    pages_per_chunk = int(request.form.get('pages_per_chunk', 5))
    
    # Generate unique ID for this job
    job_id = str(uuid.uuid4())
    
    # Save the file
    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_{filename}")
    file.save(file_path)
    
    # Start processing in a separate thread
    thread = threading.Thread(target=process_pdf, args=(file_path, job_id, pages_per_chunk))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'job_id': job_id,
        'message': 'File uploaded successfully. Translation started.'
    })

@app.route('/progress/<job_id>', methods=['GET'])
def get_progress(job_id):
    if job_id not in translation_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = translation_jobs[job_id]
    
    # Calculate elapsed time
    elapsed_time = time.time() - job.get('start_time', time.time())  # استفاده از get برای جلوگیری از خطا
    
    # Estimate remaining time based on progress
    remaining_time = None
    if job['progress'] > 0:
        remaining_time = (elapsed_time / job['progress']) * (100 - job['progress'])
    
    response = {
        'status': job['status'],
        'progress': job['progress'],
        'total_pages': job.get('total_pages', 0),  # استفاده از get برای جلوگیری از خطا
        'elapsed_time': elapsed_time,
        'remaining_time': remaining_time,
        'chunks': []
    }
    
    # Add chunk information
    for chunk in job.get('chunks', []):  # استفاده از get برای جلوگیری از خطا
        chunk_info = {
            'chunk_index': chunk['chunk_index'],
            'status': chunk['status'],
            'pages': [page['page_num'] for page in chunk['pages']]
        }
        
        if chunk['status'] == 'completed':
            chunk_info['translated_text'] = chunk['translated_text']
        elif chunk['status'] == 'failed':
            chunk_info['error'] = chunk.get('error', 'Unknown error')
            
        response['chunks'].append(chunk_info)
    
    # Add PDF path if available
    if job['status'] == 'completed' and 'pdf_path' in job:
        response['pdf_url'] = f"/download/{job_id}"
    
    return jsonify(response)

@app.route('/download/<job_id>', methods=['GET'])
def download_file(job_id):
    if job_id not in translation_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = translation_jobs[job_id]
    
    if job['status'] != 'completed' or 'pdf_path' not in job:
        return jsonify({'error': 'Translation not completed yet'}), 400
    
    return send_file(job['pdf_path'], as_attachment=True, download_name="translated_document.pdf")

@app.route('/text/<job_id>', methods=['GET'])
def get_text(job_id):
    if job_id not in translation_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = translation_jobs[job_id]
    
    if job['status'] != 'completed':
        return jsonify({'error': 'Translation not completed yet'}), 400
    
    # Combine all translated text
    all_text = ""
    for chunk in job['chunks']:
        if chunk['status'] == 'completed':
            all_text += chunk['translated_text'] + "\n\n"
    
    response = {
        'text': all_text
    }
    
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)