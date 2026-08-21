import os
import time
import urllib.request
import threading

def run_self_ping():
    """
    Background worker thread that pings the Render app URL every 10 minutes (600s).
    Prevents Render free tier instances from sleeping due to 15-minute inactivity timeout.
    """
    # Wait 20s after app launch before starting ping loop
    time.sleep(20)
    
    app_url = os.environ.get('RENDER_EXTERNAL_URL', '')
    if not app_url:
        app_url = 'http://127.0.0.1:8000'
    
    ping_endpoint = f"{app_url.rstrip('/')}/ping/"
    print(f"[Keep-Alive Engine] Starting background self-ping thread for endpoint: {ping_endpoint}")

    while True:
        try:
            req = urllib.request.Request(ping_endpoint, headers={'User-Agent': 'RenderKeepAlivePinger/1.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    print(f"[Keep-Alive Engine] Self-ping status 200 OK at {time.strftime('%H:%M:%S')}")
        except Exception as e:
            # Silent catch to avoid spamming logs
            pass
        
        # Sleep for 10 minutes (600 seconds)
        time.sleep(600)

def start_keep_alive_thread():
    """Start daemon thread for background self-ping."""
    # Ensure thread starts only once in production
    if os.environ.get('RUN_MAIN') == 'true' or os.environ.get('RENDER') == 'true' or not os.environ.get('SERVER_GATEWAY'):
        t = threading.Thread(target=run_self_ping, daemon=True)
        t.start()
