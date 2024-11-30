import os
import base64
import uuid
import json
from flask import Flask, request, render_template, send_file, jsonify, send_from_directory
import qrcode
from PIL import Image
from qrcode.image.styledpil import StyledPilImage
import io
import secrets
from pyzbar.pyzbar import decode

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# In-memory token storage (replace with a database in production)
tokens = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<path:filename>')
def serve_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

def generate_token():
    return secrets.token_urlsafe(16)

def compress_image(image, max_size=(100, 100), quality=60):
    # Open the image
    img = Image.open(image)
    
    # Convert RGBA to RGB if necessary
    if img.mode == "RGBA":
        img = img.convert("RGB")
    
    # Resize the image to the max_size while maintaining aspect ratio
    img.thumbnail(max_size)
    
    # Save the compressed image to a BytesIO object
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
    
    # Return the compressed image as bytes
    return img_byte_arr.getvalue()

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    custom_name = request.form.get('customName', '').strip()
    
    # Compress the image
    compressed_img_data = compress_image(file)
    
    # Generate token
    token = generate_token()
    
    # Encode the compressed image data
    img_data = base64.b64encode(compressed_img_data).decode('utf-8')
    
    # Generate a QR code containing the token and image data
    qr_data = json.dumps({
        'token': token,
        'image_data': img_data
    })
    qr = qrcode.QRCode(version=None, box_size=10, border=4, error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white", image_factory=StyledPilImage)
    
    # Save the image to a BytesIO object
    img_io = io.BytesIO()
    qr_img.save(img_io, format='PNG')
    img_io.seek(0)  # Rewind to the beginning of the image
    
    # Convert image to base64
    qr_img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
    
    #qr_filename = os.path.join(folder_path, 'qr_code.png')
    #qr_img.save(qr_filename)
    
    # Store token and image data (in production, use a database)
    tokens[token] = img_data
    
    return jsonify({
        'qrCode': qr_img_base64,
        'token': token
    }), 200

@app.route('/decode', methods=['POST'])
def decode_qr():
    print('hi')
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    token = request.form.get('token', '').strip()
    if not token:
        return jsonify({'error': 'No token provided'}), 400
    
    try:
        # Decode the QR code from the uploaded image
        img = Image.open(file.stream)

        # Use pyzbar to decode the QR code from the image
        qr_codes = decode(img)

        if not qr_codes:
            return jsonify({'error': 'No QR code found in the image'}), 400
        
        # Extract the data from the first QR code found (in case there are multiple QR codes)
        decoded_data = qr_codes[0].data.decode('utf-8')
        decoded_data = json.loads(decoded_data)

        # Verify that the token matches
        if decoded_data['token'] != token:
            return jsonify({'error': 'Invalid token'}), 400
        
        if token not in tokens:
            return jsonify({'error': 'Token not found'}), 400
        
        # Retrieve the image data associated with the token
        img_data = base64.b64decode(tokens[token])
        
        # Create an in-memory file-like object
        img_io = io.BytesIO(img_data)
        img_io.seek(0)
        
        # Send the image file
        return send_file(img_io, mimetype='image/jpeg')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)

