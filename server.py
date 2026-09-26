import json
import subprocess
import urllib.parse
from flask import Flask, Response, jsonify, request
import yt_dlp

app = Flask(__name__)

ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch1',
    'extract_flat': False,
}

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'xiaozhi-youtube-bridge'})

@app.route('/stream_pcm')
@app.route('/search')
def search():
    song = request.args.get('song') or request.args.get('q', '')
    if not song:
        return jsonify({'error': 'Missing song parameter'}), 400
    
    query = f"ytsearch1:{song}"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if not info or 'entries' not in info or not info['entries']:
                return jsonify({'found': False, 'message': 'Not found'}), 404
            entry = info['entries'][0]
            title = entry.get('title', song)
            artist = entry.get('uploader') or entry.get('channel', 'YouTube')
            duration = int(entry.get('duration', 0) or 0)
            vid_id = entry.get('id')
            host = request.host
            proto = request.headers.get('X-Forwarded-Proto', 'http')
            audio_url = f"{proto}://{host}/stream.mp3?id={vid_id}"
            return jsonify({
                'found': True,
                'title': title,
                'artist': artist,
                'audio_url': audio_url,
                'duration': duration,
                'id': vid_id
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stream.mp3')
@app.route('/stream')
def stream_audio():
    vid_id = request.args.get('id')
    if not vid_id:
        return 'Missing id', 400
    
    url = f"https://www.youtube.com/watch?v={vid_id}"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            stream_url = info.get('url')
        
        cmd = [
            'ffmpeg', '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
            '-i', stream_url,
            '-vn', '-c:a', 'libmp3lame', '-b:a', '128k', '-f', 'mp3',
            'pipe:1'
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=16384)
        
        def generate():
            try:
                while True:
                    data = proc.stdout.read(4096)
                    if not data:
                        break
                    yield data
            finally:
                proc.terminate()
        
        return Response(generate(), mimetype='audio/mpeg')
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8888))
    app.run(host='0.0.0.0', port=port)
