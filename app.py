from flask import Flask, request, jsonify, send_file
from pytube import YouTube
import os
import uuid
import logging
from werkzeug.exceptions import BadRequest

app = Flask(__name__)
app.config['DOWNLOAD_FOLDER'] = 'downloads'

# Ensure download directory exists
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/api/info', methods=['GET'])
def get_video_info():
    url = request.args.get('url')
    
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400
    
    try:
        yt = YouTube(url)
        
        # Get available streams
        streams = []
        for stream in yt.streams.filter(progressive=True):
            streams.append({
                "itag": stream.itag,
                "resolution": stream.resolution,
                "mime_type": stream.mime_type,
                "fps": stream.fps,
                "size_mb": round(stream.filesize / (1024 * 1024), 2)
            })
        
        video_info = {
            "title": yt.title,
            "author": yt.author,
            "length_seconds": yt.length,
            "views": yt.views,
            "thumbnail_url": yt.thumbnail_url,
            "streams": streams
        }
        
        return jsonify(video_info)
    
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/download', methods=['GET'])
def download_video():
    url = request.args.get('url')
    itag = request.args.get('itag')
    
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400
    
    try:
        yt = YouTube(url)
        
        # Generate a unique filename
        filename = f"{uuid.uuid4().hex}.mp4"
        file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
        
        # Download the video
        if itag:
            stream = yt.streams.get_by_itag(int(itag))
            if not stream:
                return jsonify({"error": f"Stream with itag {itag} not found"}), 404
        else:
            # Default to highest resolution
            stream = yt.streams.get_highest_resolution()
        
        logger.info(f"Downloading video: {yt.title}")
        stream.download(output_path=app.config['DOWNLOAD_FOLDER'], filename=filename)
        
        # Return the file
        return send_file(file_path, as_attachment=True, download_name=f"{yt.title}.mp4")
    
    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/download/audio', methods=['GET'])
def download_audio():
    url = request.args.get('url')
    
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400
    
    try:
        yt = YouTube(url)
        
        # Generate a unique filename
        filename = f"{uuid.uuid4().hex}.mp3"
        file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
        
        # Download audio only
        stream = yt.streams.filter(only_audio=True).first()
        
        logger.info(f"Downloading audio: {yt.title}")
        stream.download(output_path=app.config['DOWNLOAD_FOLDER'], filename=filename)
        
        # Return the file
        return send_file(file_path, as_attachment=True, download_name=f"{yt.title}.mp3")
    
    except Exception as e:
        logger.error(f"Error downloading audio: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.errorhandler(BadRequest)
def handle_bad_request(e):
    return jsonify({"error": str(e)}), 400

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # Use environment variable for port with a default of 5000
    port = int(os.environ.get('PORT', 5000))
    # In production, set debug to False
    app.run(host='0.0.0.0', port=port, debug=False)
