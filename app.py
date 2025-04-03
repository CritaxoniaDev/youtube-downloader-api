from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
import yt_dlp
import os
import uuid
import logging
from werkzeug.exceptions import BadRequest

app = Flask(__name__)
# Enable CORS for all routes
CORS(app)
app.config['DOWNLOAD_FOLDER'] = 'downloads'

# Ensure download directory exists
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Swagger configuration
SWAGGER_URL = '/api/docs'  # URL for exposing Swagger UI
API_URL = '/static/swagger.json'  # Our API url (can of course be a local resource)

# Call factory function to create our blueprint
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,  
    API_URL,
    config={  # Swagger UI config overrides
        'app_name': "YouTube Downloader API"
    }
)

# Register blueprint at URL
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# Create a static folder if it doesn't exist
os.makedirs('static', exist_ok=True)

# Create a swagger.json file with API documentation
swagger_json = {
    "swagger": "2.0",
    "info": {
        "title": "YouTube Downloader API",
        "description": "API for downloading YouTube videos and audio",
        "version": "1.0"
    },
    "basePath": "/api",
    "schemes": [
        "http",
        "https"
    ],
    "paths": {
        "/info": {
            "get": {
                "summary": "Get YouTube video information",
                "description": "Returns information about a YouTube video",
                "parameters": [
                    {
                        "name": "url",
                        "in": "query",
                        "description": "YouTube video URL",
                        "required": True,
                        "type": "string"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Video information"
                    },
                    "400": {
                        "description": "Bad request"
                    },
                    "500": {
                        "description": "Internal server error"
                    }
                }
            }
        },
        "/download": {
            "get": {
                "summary": "Download YouTube video",
                "description": "Downloads a YouTube video",
                "parameters": [
                    {
                        "name": "url",
                        "in": "query",
                        "description": "YouTube video URL",
                        "required": True,
                        "type": "string"
                    },
                    {
                        "name": "itag",
                        "in": "query",
                        "description": "Stream itag",
                        "required": False,
                        "type": "integer"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Video file"
                    },
                    "400": {
                        "description": "Bad request"
                    },
                    "404": {
                        "description": "Stream not found"
                    },
                    "500": {
                        "description": "Internal server error"
                    }
                }
            }
        },
        "/download/audio": {
            "get": {
                "summary": "Download YouTube audio",
                "description": "Downloads audio from a YouTube video",
                "parameters": [
                    {
                        "name": "url",
                        "in": "query",
                        "description": "YouTube video URL",
                        "required": True,
                        "type": "string"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Audio file"
                    },
                    "400": {
                        "description": "Bad request"
                    },
                    "500": {
                        "description": "Internal server error"
                    }
                }
            }
        }
    }
}

# Write the swagger.json file
with open('static/swagger.json', 'w') as f:
    import json
    json.dump(swagger_json, f)

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

@app.route('/api/download/ytdlp', methods=['GET'])
def download_video_ytdlp():
    url = request.args.get('url')
    
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400
    
    try:
        # Generate a unique filename
        filename = f"{uuid.uuid4().hex}.mp4"
        file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
        
        ydl_opts = {
            'format': 'best',
            'outtmpl': file_path,
            # Add cookies file if available
            'cookiefile': 'youtube_cookies.txt' if os.path.exists('youtube_cookies.txt') else None,
            # Add user agent to mimic a browser
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get('title', 'video')
        
        # Return the file
        return send_file(file_path, as_attachment=True, download_name=f"{video_title}.mp4")
    
    except Exception as e:
        logger.error(f"Error downloading video with yt-dlp: {str(e)}")
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

@app.route('/favicon.ico')
def favicon():
    return "", 204  # Return no content

if __name__ == '__main__':
    # Use environment variable for port with a default of 5000
    port = int(os.environ.get('PORT', 5000))
    # In production, set debug to False
    app.run(host='0.0.0.0', port=port, debug=False)
