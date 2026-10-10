"""
YouTube Auto-Uploader - 100% FREE using YouTube Data API v3
Setup: https://console.cloud.google.com/ → Create project → Enable YouTube Data API v3
"""
import json
import os
import sys
import pickle
from datetime import datetime


# ─── YOUTUBE CREDENTIALS ──────────────────────────────────────────────────────
# 1. Go to https://console.cloud.google.com/
# 2. Create project → Enable "YouTube Data API v3"
# 3. Create OAuth 2.0 credentials → Download as client_secrets.json
# 4. Place client_secrets.json in project root
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = "assets/youtube_token.pkl"


def get_authenticated_service():
    """Get authenticated YouTube API service."""
    try:
        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
    except ImportError:
        print("❌ Install: pip install google-api-python-client google-auth-oauthlib")
        sys.exit(1)
    
    credentials = None
    
    # Load saved credentials
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as f:
            credentials = pickle.load(f)
    
    # Refresh or get new credentials
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print(f"❌ Missing {CLIENT_SECRETS_FILE}")
                print("   Download from: https://console.cloud.google.com/ → APIs & Services → Credentials")
                sys.exit(1)
            
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)
        
        # Save credentials for next time
        with open(TOKEN_FILE, 'wb') as f:
            pickle.dump(credentials, f)
    
    return build('youtube', 'v3', credentials=credentials)


def upload_video(video_path: str, script_data: dict, mode: str = "upload") -> str:
    """Upload video to YouTube as a Short."""
    
    if mode == "save_only":
        print(f"💾 SAVE ONLY MODE: Video saved at {video_path}")
        print("   To upload: run with mode='upload' after setting up YouTube API")
        return video_path
    
    print("📤 Uploading to YouTube...")
    
    try:
        youtube = get_authenticated_service()
        from googleapiclient.http import MediaFileUpload
    except SystemExit:
        print(f"💾 Video saved locally: {video_path}")
        return video_path
    
    title = script_data.get("title", "GTA 6 HUGE News Update! 🎮")
    description = script_data.get("description", "#GTA6 #Shorts")
    tags = script_data.get("tags", ["GTA6", "Shorts", "Gaming"])
    
    # Ensure title isn't too long
    title = title[:90] if len(title) > 90 else title
    
    # Add #Shorts to description for YouTube algorithm
    if "#Shorts" not in description:
        description = "#Shorts #GTA6\n\n" + description
    
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': '20',  # Gaming category
            'defaultLanguage': 'en',
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False,
        }
    }
    
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype='video/mp4')
    
    request = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"   Uploading... {int(status.progress() * 100)}%")
    
    video_id = response['id']
    video_url = f"https://www.youtube.com/shorts/{video_id}"
    
    print(f"\n✅ UPLOADED SUCCESSFULLY!")
    print(f"   Title: {title}")
    print(f"   URL: {video_url}")
    
    return video_url


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    import glob
    videos = sorted(glob.glob("output/*.mp4"), key=os.path.getmtime, reverse=True)
    
    if not videos:
        print("No videos found in output/")
        sys.exit(1)
    
    with open("assets/current_script.json") as f:
        script_data = json.load(f)
    
    result = upload_video(videos[0], script_data, mode="upload")
    print(f"Result: {result}")
