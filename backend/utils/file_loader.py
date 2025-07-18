import io
import pdfplumber
from PIL import Image
import pytesseract
import logging
import pandas as pd
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
import tempfile
from openai import OpenAI
import os

from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_pdf(file_bytes):
    """
    Extract text from PDF file bytes using pdfplumber
    """
    try:
        # Create a BytesIO object from the file bytes
        pdf_file = io.BytesIO(file_bytes)
        
        text_content = []
        
        with pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                try:
                    # Extract text from each page
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(f"--- Page {page_num + 1} ---")
                        text_content.append(page_text.strip())
                except Exception as e:
                    logger.warning(f"Could not extract text from page {page_num + 1}: {e}")
                    continue
        
        if not text_content:
            return "No text content found in PDF"
        
        return "\n\n".join(text_content)
    
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        return f"Error processing PDF: {str(e)}"

def load_image(file_bytes):
    """
    Extract text from image file bytes using OCR (pytesseract)
    """
    try:
        # Create PIL Image from bytes
        image = Image.open(io.BytesIO(file_bytes))
        
        # Convert to RGB if necessary (some formats might be RGBA or grayscale)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Use pytesseract to extract text
        extracted_text = pytesseract.image_to_string(image)
        
        # Clean up the extracted text
        cleaned_text = extracted_text.strip()
        
        if not cleaned_text:
            return "No text found in image"
        
        return cleaned_text
    
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        return f"Error processing image: {str(e)}"

def load_text(file_bytes):
    """
    Load plain text from file bytes
    """
    try:
        # Try different encodings
        encodings = ['utf-8', 'utf-16', 'latin-1', 'ascii']
        
        for encoding in encodings:
            try:
                text = file_bytes.decode(encoding)
                return text.strip()
            except UnicodeDecodeError:
                continue
        
        # If all encodings fail, try with error handling
        text = file_bytes.decode('utf-8', errors='replace')
        return text.strip()
    
    except Exception as e:
        logger.error(f"Error processing text file: {e}")
        return f"Error processing text file: {str(e)}"
    
def load_csv(file_bytes):
    """
    Extract data from CSV file bytes and convert to readable text
    """
    try:
        # Create StringIO from bytes
        csv_data = io.StringIO(file_bytes.decode('utf-8'))
        
        # Read CSV with pandas
        df = pd.read_csv(csv_data)
        
        # Convert to a readable text format
        text_content = []
        
        # Add basic info about the data
        text_content.append(f"CSV Data Summary:")
        text_content.append(f"Rows: {len(df)}, Columns: {len(df.columns)}")
        text_content.append(f"Column Names: {', '.join(df.columns.tolist())}")
        text_content.append("")
        
        # Add sample of the data (first 10 rows)
        text_content.append("Sample Data (first 10 rows):")
        sample_data = df.head(10).to_string(index=False)
        text_content.append(sample_data)
        
        # Add summary statistics for numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            text_content.append("")
            text_content.append("Numeric Column Summary:")
            for col in numeric_cols:
                stats = df[col].describe()
                text_content.append(f"{col}: Mean={stats['mean']:.2f}, Min={stats['min']:.2f}, Max={stats['max']:.2f}")
        
        return "\n".join(text_content)
    
    except Exception as e:
        logger.error(f"Error processing CSV: {e}")
        return f"Error processing CSV: {str(e)}"

def load_excel(file_bytes):
    """
    Extract data from Excel file bytes and convert to readable text
    """
    try:
        # Create BytesIO object
        excel_file = io.BytesIO(file_bytes)
        
        # Read all sheets
        excel_data = pd.read_excel(excel_file, sheet_name=None)  # None reads all sheets
        
        text_content = []
        text_content.append("Excel File Summary:")
        text_content.append(f"Number of sheets: {len(excel_data)}")
        text_content.append("")
        
        # Process each sheet
        for sheet_name, df in excel_data.items():
            text_content.append(f"=== Sheet: {sheet_name} ===")
            text_content.append(f"Rows: {len(df)}, Columns: {len(df.columns)}")
            text_content.append(f"Column Names: {', '.join(df.columns.astype(str).tolist())}")
            text_content.append("")
            
            # Add sample data (first 5 rows per sheet to avoid too much text)
            text_content.append("Sample Data (first 5 rows):")
            sample_data = df.head(5).to_string(index=False)
            text_content.append(sample_data)
            
            # Add summary for numeric columns
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                text_content.append("")
                text_content.append("Numeric Summary:")
                for col in numeric_cols:
                    if not df[col].isna().all():  # Skip if all values are NaN
                        stats = df[col].describe()
                        text_content.append(f"{col}: Mean={stats['mean']:.2f}, Min={stats['min']:.2f}, Max={stats['max']:.2f}")
            
            text_content.append("")  # Space between sheets
        
        return "\n".join(text_content)
    
    except Exception as e:
        logger.error(f"Error processing Excel: {e}")
    

def load_video(file_bytes):
    pass
    """
    Extract audio from video file bytes and transcribe to text using OpenAI Whisper
    """
    try:
        # Create temporary files for video processing
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            temp_video.write(file_bytes)
            temp_video_path = temp_video.name
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
            temp_audio_path = temp_audio.name
        
        try:
            # Extract audio from video using moviepy
            logger.info("Extracting audio from video...")
            with VideoFileClip(temp_video_path) as video:
                # Extract audio and save as WAV
                audio = video.audio
                if audio is None:
                    return "No audio track found in video"
                
                audio.write_audiofile(temp_audio_path, verbose=False, logger=None)
                
                # Get video duration for context
                duration = video.duration
                logger.info(f"Video duration: {duration:.2f} seconds")
            
            # Transcribe audio using OpenAI Whisper
            logger.info("Transcribing audio to text...")
            with open(temp_audio_path, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                )
            
            if not transcript or not transcript.text.strip():
                return "No speech detected in video audio"
            
            # Format the output with metadata
            result = [
                f"--- Video Transcription ---",
                f"Duration: {duration:.2f} seconds",
                f"Transcript:",
                transcript.text.strip()
            ]
            
            return "\n\n".join(result)
            
        except Exception as e:
            logger.error(f"Error during video/audio processing: {e}")
            return f"Error processing video: {str(e)}"
        
        finally:
            # Clean up temporary files
            try:
                os.unlink(temp_video_path)
                os.unlink(temp_audio_path)
            except Exception as cleanup_error:
                logger.warning(f"Could not clean up temporary files: {cleanup_error}")
    
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        return f"Error processing video: {str(e)}"
    
def load_audio(file_bytes):
    """
    Process audio files (m4a, mp3, wav, etc.) and transcribe to text using OpenAI Whisper
    """
    try:
        # Create temporary files for audio processing
        with tempfile.NamedTemporaryFile(suffix='.m4a', delete=False) as temp_input:
            temp_input.write(file_bytes)
            temp_input_path = temp_input.name
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_output:
            temp_output_path = temp_output.name
        
        try:
            # Convert audio to WAV format for better compatibility with Whisper
            logger.info("Converting audio to WAV format...")
            audio = AudioSegment.from_file(temp_input_path)
            
            # Convert to mono and set sample rate for optimal Whisper performance
            audio = audio.set_channels(1).set_frame_rate(16000)
            audio.export(temp_output_path, format="wav")
            
            # Get audio duration for context
            duration = len(audio) / 1000.0  # Convert milliseconds to seconds
            logger.info(f"Audio duration: {duration:.2f} seconds")
            
            # Transcribe audio using OpenAI Whisper
            logger.info("Transcribing audio to text...")
            with open(temp_output_path, 'rb') as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                )
            
            if not transcript or not transcript.text.strip():
                return "No speech detected in audio file"
            
            # Format the output with metadata
            result = [
                f"--- Audio Transcription ---",
                f"Duration: {duration:.2f} seconds",
                f"Transcript:",
                transcript.text.strip()
            ]
            
            return "\n\n".join(result)
            
        except Exception as e:
            logger.error(f"Error during audio processing: {e}")
            return f"Error processing audio: {str(e)}"
        
        finally:
            # Clean up temporary files
            try:
                os.unlink(temp_input_path)
                os.unlink(temp_output_path)
            except Exception as cleanup_error:
                logger.warning(f"Could not clean up temporary files: {cleanup_error}")
    
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        return f"Error processing audio: {str(e)}"


def normalize_text(text):
    """
    Helper function to clean and normalize extracted text
    """
    if not text:
        return ""
    
    # Remove excessive whitespace
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        cleaned_line = line.strip()
        if cleaned_line:  # Only keep non-empty lines
            cleaned_lines.append(cleaned_line)
    
    return '\n'.join(cleaned_lines)