from flask import Flask, request, jsonify, send_file, redirect
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
app.config["DOWNLOAD_FOLDER"] = "downloads"

# Ensure download directory exists
os.makedirs(app.config["DOWNLOAD_FOLDER"], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        ydl_opts = {
            "format": "bestaudio/best",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "referer": "https://www.youtube.com/",
            "nocheckcertificate": True,
            "geo_bypass": True,
            "quiet": False,
            "no_warnings": False,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"],
                    "player_skip": ["webpage", "configs", "js"],
                }
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            video_info = {
                "title": info.get("title", "Unknown"),
                "author": info.get("uploader", "Unknown"),
                "length_seconds": info.get("duration", 0),
                "views": info.get("view_count", 0),
                "thumbnail_url": info.get("thumbnail", ""),
                "description": info.get("description", ""),
            }

            return jsonify(video_info)

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
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36",
            "referer": "https://www.youtube.com/",
            "nocheckcertificate": True,
            "geo_bypass": True,
            "geo_bypass_country": "US",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            audio_title = info.get("title", "audio")
            # Get the actual file path with the correct extension
            downloaded_file = ydl.prepare_filename(info)

        # Return the file with the appropriate extension
        return send_file(
            downloaded_file,
            as_attachment=True,
            download_name=f"{audio_title}.{downloaded_file.split('.')[-1]}",
        )

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


@app.route("/favicon.ico")
def favicon():
    return "", 204  # Return no content


if __name__ == "__main__":
    # Use environment variable for port with a default of 5000
    port = int(os.environ.get("PORT", 5000))
    # In production, set debug to False
    app.run(host="0.0.0.0", port=port, debug=False)
