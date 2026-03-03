"""
ZeroCD WebUI Server
Flask web interface for ISO management and WiFi configuration
"""
import os
import json
import time
import threading
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from werkzeug.utils import secure_filename
from typing import Optional, Dict

from config import (
    ISO_DIR,
    WEBUI_PORT,
    WEBUI_HOST,
    WEBUI_SECRET_KEY,
    POPULAR_ISOS,
    is_gadget_mode,
    ZEROCD_DATA_DIR,
    ensure_data_dir
)
from usb.iso_manager import ISOManager
from net.wifi import get_wifi_manager
from net.captive import get_captive_portal
from system.logger import get_logger


app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = WEBUI_SECRET_KEY

logger = get_logger("webui")

iso_manager = ISOManager(ISO_DIR)
wifi_manager = get_wifi_manager()
captive_portal = get_captive_portal()

download_tasks: Dict[str, dict] = {}


@app.before_request
def check_gadget_mode():
    """Block WebUI in USB Gadget mode to save power."""
    if is_gadget_mode() and request.endpoint not in ['static', 'captive']:
        return """
        <html><head><title>ZeroCD - Unavailable</title></head>
        <body style="font-family: sans-serif; padding: 40px; text-align: center;">
            <h1>WebUI недоступен</h1>
            <p>В режиме USB Gadget (эмуляция CD-ROM) WebUI отключён для экономии питания.</p>
            <p>Отключите USB кабель и перезагрузите устройство для использования WebUI.</p>
            <a href="/">Вернуться</a>
        </body></html>
        """, 503


@app.route('/')
def index():
    """Main page - ISO list."""
    isos = iso_manager.list_isos()
    total_size = sum(
        os.path.getsize(os.path.join(ISO_DIR, f)) 
        for f in isos if os.path.exists(os.path.join(ISO_DIR, f))
    )
    
    disk_total, disk_used, disk_free = get_disk_usage()
    
    wifi_status = wifi_manager.get_status()
    wifi_ip = wifi_manager.get_ip()
    
    return render_template('index.html',
        isos=isos,
        total_size=format_size(total_size),
        disk_used=disk_used,
        disk_total=disk_total,
        disk_percent=int(disk_used/disk_total*100) if disk_total > 0 else 0,
        wifi_connected=wifi_status.value == "connected",
        wifi_ssid=wifi_manager.get_current_ssid(),
        wifi_ip=wifi_ip,
        gadget_mode=is_gadget_mode()
    )


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """Upload ISO file from computer."""
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'No file selected'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.iso'):
            return jsonify({'error': 'Only .iso files allowed'}), 400
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(ISO_DIR, filename)
        
        os.makedirs(ISO_DIR, exist_ok=True)
        
        file.save(filepath)
        logger.info(f"Uploaded: {filename}")
        
        return jsonify({'success': True, 'filename': filename})
    
    return render_template('upload.html', gadget_mode=is_gadget_mode())


@app.route('/download')
def download_page():
    """Download ISO from URL page."""
    return render_template('download.html', 
        popular_isos=POPULAR_ISOS,
        gadget_mode=is_gadget_mode()
    )


@app.route('/api/download', methods=['POST'])
def start_download():
    """Start downloading ISO from URL."""
    data = request.get_json()
    url = data.get('url', '').strip()
    name = data.get('name', 'download.iso')
    
    if not url:
        return jsonify({'error': 'URL required'}), 400
    
    if not name.endswith('.iso'):
        name += '.iso'
    
    filename = secure_filename(name)
    filepath = os.path.join(ISO_DIR, filename)
    
    task_id = f"download_{int(time.time())}"
    download_tasks[task_id] = {
        'url': url,
        'filename': filename,
        'filepath': filepath,
        'progress': 0,
        'speed': 0,
        'status': 'starting',
        'thread': None
    }
    
    def download_task(task_id, url, filepath):
        try:
            import requests
            response = requests.get(url, stream=True, timeout=30)
            total_size = int(response.headers.get('content-length', 0))
            
            download_tasks[task_id]['status'] = 'downloading'
            download_tasks[task_id]['total'] = total_size
            
            with open(filepath, 'wb') as f:
                downloaded = 0
                last_time = time.time()
                last_downloaded = 0
                
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        current_time = time.time()
                        if current_time - last_time >= 1:
                            speed = downloaded - last_downloaded
                            download_tasks[task_id]['speed'] = speed
                            download_tasks[task_id]['progress'] = downloaded
                            download_tasks[task_id]['percent'] = int(downloaded/total_size*100) if total_size > 0 else 0
                            last_time = current_time
                            last_downloaded = downloaded
            
            download_tasks[task_id]['status'] = 'complete'
            download_tasks[task_id]['progress'] = total_size
            download_tasks[task_id]['percent'] = 100
            
        except Exception as e:
            download_tasks[task_id]['status'] = 'error'
            download_tasks[task_id]['error'] = str(e)
            if os.path.exists(filepath):
                os.remove(filepath)
    
    thread = threading.Thread(target=download_task, args=(task_id, url, filepath))
    thread.daemon = True
    thread.start()
    download_tasks[task_id]['thread'] = thread
    
    return jsonify({'success': True, 'task_id': task_id})


@app.route('/api/download/status')
def download_status():
    """Get download status."""
    return jsonify(download_tasks)


@app.route('/settings')
def settings():
    """WiFi settings page."""
    wifi_status = wifi_manager.get_status()
    wifi_ip = wifi_manager.get_ip()
    ap_config = wifi_manager.get_ap_config()
    captive_status = captive_portal.get_status()
    
    return render_template('settings.html',
        wifi_status=wifi_status.value,
        wifi_connected=wifi_status.value == "connected",
        wifi_ssid=wifi_manager.get_current_ssid(),
        wifi_ip=wifi_ip,
        ap_ssid=ap_config['ssid'],
        ap_password=ap_config['password'],
        ap_ip=ap_config['ip'],
        captive_running=captive_status['running'],
        gadget_mode=is_gadget_mode()
    )


@app.route('/api/wifi/status')
def wifi_status_api():
    """Get WiFi status JSON."""
    status = wifi_manager.get_status()
    return jsonify({
        'status': status.value,
        'connected': status.value == "connected",
        'ssid': wifi_manager.get_current_ssid(),
        'ip': wifi_manager.get_ip(),
        'has_wifi': wifi_manager.has_wifi_support()
    })


@app.route('/api/wifi/connect', methods=['POST'])
def wifi_connect():
    """Connect to WiFi network."""
    data = request.get_json()
    ssid = data.get('ssid', '').strip()
    password = data.get('password', '').strip()
    
    if not ssid:
        return jsonify({'error': 'SSID required'}), 400
    
    wifi_manager.save_network(ssid, password)
    
    if wifi_manager.connect(ssid):
        return jsonify({'success': True, 'ssid': ssid})
    else:
        return jsonify({'error': 'Connection failed'}), 500


@app.route('/api/wifi/disconnect', methods=['POST'])
def wifi_disconnect():
    """Disconnect from WiFi."""
    wifi_manager.disconnect()
    return jsonify({'success': True})


@app.route('/api/wifi/forget', methods=['POST'])
def wifi_forget():
    """Forget saved network."""
    wifi_manager.forget_network()
    return jsonify({'success': True})


@app.route('/api/wifi/scan')
def wifi_scan():
    """Scan for available networks."""
    networks = wifi_manager.scan()
    return jsonify({'networks': networks})


@app.route('/api/captive/start', methods=['POST'])
def captive_start():
    """Start captive portal (AP mode)."""
    if captive_portal.start():
        return jsonify({'success': True})
    return jsonify({'error': 'Failed to start'}), 500


@app.route('/api/captive/stop', methods=['POST'])
def captive_stop():
    """Stop captive portal."""
    captive_portal.stop()
    return jsonify({'success': True})


@app.route('/api/captive/status')
def captive_status():
    """Get captive portal status."""
    return jsonify(captive_portal.get_status())


@app.route('/api/isos')
def api_isos():
    """Get ISO list JSON."""
    isos = iso_manager.list_isos()
    result = []
    for iso in isos:
        path = iso_manager.get_iso_path(iso)
        size = os.path.getsize(path) if path and os.path.exists(path) else 0
        result.append({
            'name': iso,
            'size': format_size(size),
            'size_bytes': size
        })
    return jsonify(result)


@app.route('/api/delete', methods=['POST'])
def api_delete():
    """Delete ISO file."""
    data = request.get_json()
    filename = data.get('filename', '')
    
    path = iso_manager.get_iso_path(filename)
    if path and os.path.exists(path):
        os.remove(path)
        return jsonify({'success': True})
    
    return jsonify({'error': 'File not found'}), 404


@app.route('/api/select', methods=['POST'])
def api_select():
    """Select active ISO."""
    data = request.get_json()
    filename = data.get('filename', '')
    
    path = iso_manager.get_iso_path(filename)
    if path:
        return jsonify({'success': True, 'path': path})
    
    return jsonify({'error': 'File not found'}), 404


@app.route('/api/disk')
def api_disk():
    """Get disk usage."""
    total, used, free = get_disk_usage()
    return jsonify({
        'total': total,
        'used': used,
        'free': free,
        'percent': int(used/total*100) if total > 0 else 0
    })


def format_size(bytes_size: int) -> str:
    """Format bytes to human readable size."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def get_disk_usage():
    """Get disk usage for ISO storage."""
    try:
        stat = os.statvfs(ISO_DIR)
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        used = total - free
        return total, used, free
    except:
        return 0, 0, 0


def start_webui(host: str = WEBUI_HOST, port: int = WEBUI_PORT, debug: bool = False):
    """Start WebUI server."""
    logger.info(f"Starting WebUI on {host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)


def stop_webui():
    """Stop WebUI server (flask doesn't have native stop, use in combination with atexit)."""
    pass


if __name__ == '__main__':
    start_webui()