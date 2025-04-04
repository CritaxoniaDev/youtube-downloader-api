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

# Create cookie file from environment variable if it exists
COOKIE_FILE = os.path.join(app.config["DOWNLOAD_FOLDER"], "youtube_cookies.txt")
cookie_content = os.environ.get("YOUTUBE_COOKIES")
if cookie_content and not os.path.exists(COOKIE_FILE):
    try:
        with open(COOKIE_FILE, "w") as f:
            f.write(cookie_content)
        logger.info(f"Created cookie file from environment variable: {COOKIE_FILE}")
    except Exception as e:
        logger.error(f"Failed to create cookie file: {str(e)}")

# Load YouTube API keys from environment variables
YOUTUBE_API_KEYS = []

# Try to load from individual environment variables
for i in range(1, 11):
    key = os.environ.get(f"YOUTUBE_API_KEY_{i}")
    if key and key.strip() and key != f"YOUR_API_KEY_{i}":
        YOUTUBE_API_KEYS.append(key.strip())

# Alternative: Try to load from a single comma-separated environment variable
if not YOUTUBE_API_KEYS:
    api_keys_str = os.environ.get("YOUTUBE_API_KEYS", "")
    if api_keys_str:
        YOUTUBE_API_KEYS = [
            key.strip() for key in api_keys_str.split(",") if key.strip()
        ]

# Fallback to hardcoded keys if no environment variables (not recommended for production)
if not YOUTUBE_API_KEYS:
    logger.warning(
        "No YouTube API keys found in environment variables! Using fallback keys."
    )
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

# Log the number of API keys loaded
logger.info(f"Loaded {len(YOUTUBE_API_KEYS)} YouTube API keys")

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
    if not YOUTUBE_API_KEYS:
        raise ValueError("No YouTube API keys available")
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
        "/check-ffmpeg": {
            "get": {
                "summary": "Check FFmpeg availability",
                "description": "Checks if FFmpeg is available on the server",
                "responses": {
                    "200": {"description": "FFmpeg status"},
                    "500": {"description": "Internal server error"},
                },
            }
        },
        "/api-keys": {
            "get": {
                "summary": "Check API keys status",
                "description": "Returns information about loaded API keys (non-sensitive)",
                "responses": {
                    "200": {"description": "API keys status"},
                },
            }
        },
        "/check-cookies": {
            "get": {
                "summary": "Check YouTube cookies status",
                "description": "Checks if YouTube cookies are available",
                "responses": {
                    "200": {"description": "Cookies status"},
                    "404": {"description": "Cookies not found"},
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
        youtube = build("youtube", "v3", developerKey=api_key)

        # Get video details
        video_response = (
            youtube.videos()
            .list(part="snippet,contentDetails,statistics", id=video_id)
            .execute()
        )

        if not video_response["items"]:
            return jsonify({"error": "Video not found"}), 404

        video = video_response["items"][0]

        # Format response
        video_info = {
            "title": video["snippet"]["title"],
            "author": video["snippet"]["channelTitle"],
            "description": video["snippet"]["description"],
            "thumbnail_url": video["snippet"]["thumbnails"]["high"]["url"],
            "views": int(video["statistics"].get("viewCount", 0)),
            "length_seconds": convert_duration(video["contentDetails"]["duration"]),
        }

        return jsonify(video_info)

    except HttpError as e:
        if e.resp.status == 403:
            logger.error(f"YouTube API quota exceeded or API key invalid: {str(e)}")
            return (
                jsonify({"error": "YouTube API quota exceeded or API key invalid"}),
                429,
            )
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
            # Use a more flexible format specification
            "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio[ext=webm]/bestaudio/best[height<=480]",
            "outtmpl": file_path,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "quiet": False,  # Set to False to see more debug info
            "verbose": True,  # Add verbose output
            "no_warnings": False,  # Show warnings
            "user_agent": user_agent,
            "referer": "https://www.youtube.com/",
            "nocheckcertificate": True,
            "geo_bypass": True,
            "geo_bypass_country": "US",
            # Add these options to help bypass bot detection
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"],
                    "player_skip": ["webpage", "configs", "js"],
                    "max_comments": [0],  # Don't fetch comments
                }
            },
            # Add sleep between requests
            "sleep_interval": 1,
            "max_sleep_interval": 5,
            # Add retries
            "retries": 10,
            "fragment_retries": 10,
            "skip_unavailable_fragments": True,
        }
        
        # Add cookies if available
        if os.path.exists(COOKIE_FILE):
            ydl_opts["cookiefile"] = COOKIE_FILE
            logger.info(f"Using cookie file: {COOKIE_FILE}")
        else:
            logger.warning("No cookie file available")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First, get info without downloading to check formats
            try:
                info_dict = ydl.extract_info(url, download=False)
                logger.info(f"Available formats: {len(info_dict.get('formats', []))}")
                
                # Now download the audio
                info = ydl.extract_info(url, download=True)
                audio_title = info.get('title', 'audio')
                
                # Get the actual file path with the correct extension
                downloaded_file = ydl.prepare_filename(info).replace(
                    os.path.splitext(ydl.prepare_filename(info))[1], ".mp3"
                )
                
                # Check if file exists
                if not os.path.exists(downloaded_file):
                    logger.warning(f"Expected MP3 file not found at: {downloaded_file}")
                    # Try to find the file with a different extension
                    base_path = os.path.splitext(downloaded_file)[0]
                    for ext in ['.mp3', '.m4a', '.webm', '.opus', '.mp4']:
                        alt_path = f"{base_path}{ext}"
                        if os.path.exists(alt_path):
                            logger.info(f"Found file with different extension: {alt_path}")
                            downloaded_file = alt_path
                            break
            except Exception as e:
                # If format selection fails, try with default format
                logger.warning(f"Error with format selection: {str(e)}")
                ydl_opts["format"] = "best"  # Fallback to best available format
                info = ydl.extract_info(url, download=True)
                audio_title = info.get('title', 'audio')
                downloaded_file = ydl.prepare_filename(info)
                
                # Convert to MP3 if not already
                if not downloaded_file.endswith('.mp3'):
                    import subprocess
                    mp3_file = f"{os.path.splitext(downloaded_file)[0]}.mp3"
                    subprocess.run([
                        "ffmpeg", "-i", downloaded_file, "-vn", 
                        "-ar", "44100", "-ac", "2", "-b:a", "192k", 
                        mp3_file
                    ])
                    downloaded_file = mp3_file

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

        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, check=True
        )
        return jsonify(
            {
                "status": "success",
                "ffmpeg_available": True,
                "version_info": result.stdout.split("\n")[0],
            }
        )
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        return (
            jsonify({"status": "error", "ffmpeg_available": False, "error": str(e)}),
            500,
        )


@app.route("/api/api-keys")
def api_keys_status():
    """Endpoint to check API keys status (without revealing the actual keys)"""
    return jsonify(
        {
            "api_keys_count": len(YOUTUBE_API_KEYS),
            "api_keys_available": len(YOUTUBE_API_KEYS) > 0,
            "api_keys_source": (
                "environment"
                if os.environ.get("YOUTUBE_API_KEY_1")
                or os.environ.get("YOUTUBE_API_KEYS")
                else "fallback"
            ),
        }
    )


@app.route("/api/check-cookies")
def check_cookies():
    """Endpoint to check if YouTube cookies are available"""
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r") as f:
                first_line = f.readline().strip()
                line_count = (
                    sum(1 for _ in f) + 1
                )  # +1 for the first line we already read

            return jsonify(
                {
                    "status": "success",
                    "cookies_available": True,
                    "file_path": COOKIE_FILE,
                    "file_size": os.path.getsize(COOKIE_FILE),
                    "line_count": line_count,
                    "first_line_preview": (
                        first_line[:20] + "..." if len(first_line) > 20 else first_line
                    ),
                }
            )
        except Exception as e:
            return (
                jsonify(
                    {
                        "status": "error",
                        "cookies_available": True,
                        "error": f"File exists but couldn't read it: {str(e)}",
                    }
                ),
                500,
            )
    else:
        # Check if we have cookies in environment variable
        cookie_content = os.environ.get("YOUTUBE_COOKIES")
        if cookie_content:
            return jsonify(
                {
                    "status": "warning",
                    "cookies_available": False,
                    "cookies_in_env": True,
                    "message": "Cookies found in environment variable but file not created yet",
                }
            )
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "cookies_available": False,
                        "cookies_in_env": False,
                        "error": f"Cookie file not found at {COOKIE_FILE} and no cookies in environment variable",
                    }
                ),
                404,
            )


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
