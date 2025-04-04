from flask import Flask, request, jsonify, send_file, redirect
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import yt_dlp
import os
import uuid
import logging
import random
import isodate
import re
from werkzeug.exceptions import BadRequest

app = Flask(__name__)
# Enable CORS for all routes
CORS(app)
app.config["DOWNLOAD_FOLDER"] = "downloads"

# Ensure download directory exists
os.makedirs(app.config["DOWNLOAD_FOLDER"], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# YouTube API keys - rotate between these
YOUTUBE_API_KEYS = [
    "YOUR_API_KEY_1",
    "YOUR_API_KEY_2",
    "YOUR_API_KEY_3",
    "YOUR_API_KEY_4",
    "YOUR_API_KEY_5",
    "YOUR_API_KEY_6",
    "YOUR_API_KEY_7",
    "YOUR_API_KEY_8",
    "YOUR_API_KEY_9",
    "YOUR_API_KEY_10",
]

# List of user agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36 Edg/92.0.902.84",
]

# Function to get a random API key
def get_random_api_key():
    return random.choice(YOUTUBE_API_KEYS)

# Function to get a random user agent
def get_random_user_agent():
    return random.choice(USER_AGENTS)

# Helper function to extract video ID from URL
def extract_video_id(url):
    if "youtube.com/watch" in url:
        return url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    else:
        raise ValueError("Invalid YouTube URL")

# Helper function to convert ISO 8601 duration to seconds
def convert_duration(duration):
    return int(isodate.parse_duration(duration).total_seconds())

# Swagger configuration
SWAGGER_URL = "/api/docs"  # URL for exposing Swagger UI
API_URL = "/static/swagger.json"  # Our API url

# Call factory function to create our blueprint
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={"app_name": "YouTube Downloader API"},  # Swagger UI config overrides
)

# Register blueprint at URL
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# Create a static folder if it doesn't exist
os.makedirs("static", exist_ok=True)

# Create a swagger.json file with API documentation
swagger_json = {
    "swagger": "2.0",
    "info": {
        "title": "YouTube Downloader API",
        "description": "API for downloading YouTube audio as MP3",
        "version": "1.0",
    },
    "basePath": "/api",
    "schemes": ["http", "https"],
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
                        "type": "string",
                    }
                ],
                "responses": {
                    "200": {"description": "Video information"},
                    "400": {"description": "Bad request"},
                    "500": {"description": "Internal server error"},
                },
            }
        },
        "/download/audio": {
            "get": {
                "summary": "Download YouTube audio",
                "description": "Downloads audio from a YouTube video as MP3",
                "parameters": [
                    {
                        "name": "url",
                        "in": "query",
                        "description": "YouTube video URL",
                        "required": True,
                        "type": "string",
                    }
                ],
                "responses": {
                    "200": {"description": "Audio file"},
                    "400": {"description": "Bad request"},
                    "500": {"description": "Internal server error"},
                },
            }
        },
    },
}

# Write the swagger.json file
with open("static/swagger.json", "w") as f:
    import json

    json.dump(swagger_json, f)


@app.route("/")
def index():
    return redirect("/api/docs")


@app.route("/api/info", methods=["GET"])
def get_video_info():
    url = request.args.get("url")

    if not url:
        return jsonify({"error": "URL parameter is required"}), 400

    try:
        # Extract video ID from URL
        video_id = extract_video_id(url)
        
        # Get a random API key
        api_key = get_random_api_key()
        
        # Create YouTube API client
        youtube = build('youtube', 'v3', developerKey=api_key)
        
        # Get video details
        video_response = youtube.videos().list(
            part='snippet,contentDetails,statistics',
            id=video_id
        ).execute()
        
        if not video_response['items']:
            return jsonify({"error": "Video not found"}), 404
            
        video = video_response['items'][0]
        
        # Format response
        video_info = {
            "title": video['snippet']['title'],
            "author": video['snippet']['channelTitle'],
            "description": video['snippet']['description'],
            "thumbnail_url": video['snippet']['thumbnails']['high']['url'],
            "views": int(video['statistics'].get('viewCount', 0)),
            "length_seconds": convert_duration(video['contentDetails']['duration']),
        }
        
        return jsonify(video_info)
        
    except HttpError as e:
        if e.resp.status == 403:
            logger.error(f"YouTube API quota exceeded or API key invalid: {str(e)}")
            return jsonify({"error": "YouTube API quota exceeded or API key invalid"}), 429
        else:
            logger.error(f"YouTube API error: {str(e)}")
            return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/download/audio", methods=["GET"])
def download_audio():
    url = request.args.get("url")

    if not url:
        return jsonify({"error": "URL parameter is required"}), 400

    try:
        # Generate a unique filename
        filename = f"{uuid.uuid4().hex}.%(ext)s"
        file_path = os.path.join(app.config["DOWNLOAD_FOLDER"], filename)

        # Get a random user agent
        user_agent = get_random_user_agent()

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": file_path,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "quiet": True,
            "no_warnings": True,
            "user_agent": user_agent,
            "referer": "https://www.youtube.com/",
            "nocheckcertificate": True,
            "geo_bypass": True,
            "geo_bypass_country": "US",
            # Uncomment if you have cookies
            # "cookiesfrombrowser": ("chrome", ),  # or specify browser
            # "cookiefile": "cookies.txt",  # or specify a cookies file
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First try to get info using YouTube API to avoid bot detection
            try:
                video_id = extract_video_id(url)
                api_key = get_random_api_key()
                youtube = build('youtube', 'v3', developerKey=api_key)
                video_response = youtube.videos().list(
                    part='snippet',
                    id=video_id
                ).execute()
                
                if video_response['items']:
                    video = video_response['items'][0]
                    audio_title = video['snippet']['title']
                else:
                    # Fallback to yt-dlp for info
                    info_dict = ydl.extract_info(url, download=False)
                    audio_title = info_dict.get('title', 'audio')
            except:
                # Fallback to yt-dlp for info
                info_dict = ydl.extract_info(url, download=False)
                audio_title = info_dict.get('title', 'audio')
            
            # Download the audio
            info = ydl.extract_info(url, download=True)
            
            # Get the actual file path with the correct extension
            downloaded_file = ydl.prepare_filename(info).replace(
                os.path.splitext(ydl.prepare_filename(info))[1], ".mp3"
            )

        # Return the file with the appropriate extension
        return send_file(
            downloaded_file,
            as_attachment=True,
            download_name=f"{audio_title}.mp3",
        )

    except Exception as e:
        logger.error(f"Error downloading audio: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/check-ffmpeg")
def check_ffmpeg():
    try:
        # Run ffmpeg -version command
        import subprocess
        result = subprocess.run(["ffmpeg", "-version"], 
                               capture_output=True, 
                               text=True, 
                               check=True)
        return jsonify({
            "status": "success",
            "ffmpeg_available": True,
            "version_info": result.stdout.split('\n')[0]
        })
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        return jsonify({
            "status": "error",
            "ffmpeg_available": False,
            "error": str(e)
        }), 500


@app.errorhandler(BadRequest)
def handle_bad_request(e):
    return jsonify({"error": str(e)}), 400


@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    return jsonify({"error": "Internal server error"}), 500


@app.route("/favicon.ico")
def favicon():
    return "", 204  # Return no content


if __name__ == "__main__":
    # Use environment variable for port with a default of 5000
    port = int(os.environ.get("PORT", 5000))
    # In production, set debug to False
    app.run(host="0.0.0.0", port=port, debug=False)
