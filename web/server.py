"""
ZeroCD WebUI Server
Flask web interface for ISO/IMG management and WiFi configuration
"""
import os
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
    ZEROCD_DATA_DIR
)
from usb.iso_manager import ISOManager
from net.wifi import get_wifi_manager
from net.captive import get_captive_portal
from system.logger import get_logger

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = WEBUI_SECRET_KEY

@app.template_filter('format_size')
def format_size_filter(bytes_size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"

logger = get_logger("webui")

iso_manager = ISOManager(ISO_DIR)
wifi_manager = get_wifi_manager()
captive_portal = get_captive_portal()

download_tasks: Dict[str, dict] = {}

@app.route('/')
def index():
    iso_names = iso_manager.list_isos()
    isos =[]
    total_size = 0
    
    # ИСПРАВЛЕНИЕ: Формируем список словарей с именами И размерами каждого файла
    for f in iso_names:
        path = os.path.join(ISO_DIR, f)
        if os.path.exists(path):
            sz = os.path.getsize(path)
            total_size += sz
            isos.append({'name': f, 'size': format_size(sz)})
    
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
        gadget_mode=False,
        format_size=format_size # Передаем функцию форматирования в шаблон
    )

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'No file selected'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not (file.filename.lower().endswith('.iso') or file.filename.lower().endswith('.img')):
            return jsonify({'error': 'Only .iso and .img files allowed'}), 400
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(ISO_DIR, filename)
        os.makedirs(ISO_DIR, exist_ok=True)
        
        file.save(filepath)
        logger.info(f"Uploaded: {filename}")
        return jsonify({'success': True, 'filename': filename})
    
    return render_template('upload.html', gadget_mode=False)

@app.route('/download')
def download_page():
    return render_template('download.html', popular_isos=POPULAR_ISOS, gadget_mode=False)

@app.route('/api/download', methods=['POST'])
def start_download():
    data = request.get_json()
    url = data.get('url', '').strip()
    name = data.get('name', 'download.iso')
    
    if not url: return jsonify({'error': 'URL required'}), 400
    
    filename = secure_filename(name)
    filepath = os.path.join(ISO_DIR, filename)
    task_id = f"download_{int(time.time())}"
    
    # ИСПРАВЛЕНИЕ: Больше не сохраняем объект потока (thread) в словарь!
    download_tasks[task_id] = {
        'url': url, 'filename': filename, 'filepath': filepath,
        'progress': 0, 'speed': 0, 'status': 'starting'
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
                            download_tasks[task_id]['speed'] = downloaded - last_downloaded
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
            if os.path.exists(filepath): os.remove(filepath)
    
    thread = threading.Thread(target=download_task, args=(task_id, url, filepath), daemon=True)
    thread.start()
    return jsonify({'success': True, 'task_id': task_id})

@app.route('/api/download/status')
def download_status():
    return jsonify(download_tasks)

@app.route('/settings')
def settings():
    wifi_status = wifi_manager.get_status()
    wifi_ip = wifi_manager.get_ip()
    ap_config = wifi_manager.get_ap_config()
    captive_status = captive_portal.get_status()
    return render_template('settings.html',
        wifi_status=wifi_status.value, wifi_connected=wifi_status.value == "connected",
        wifi_ssid=wifi_manager.get_current_ssid(), wifi_ip=wifi_ip,
        ap_ssid=ap_config['ssid'], ap_password=ap_config['password'], ap_ip=ap_config['ip'],
        captive_running=captive_status['running'], gadget_mode=False
    )

@app.route('/api/wifi/status')
def wifi_status_api():
    status = wifi_manager.get_status()
    return jsonify({
        'status': status.value, 'connected': status.value == "connected",
        'ssid': wifi_manager.get_current_ssid(), 'ip': wifi_manager.get_ip(),
        'has_wifi': wifi_manager.has_wifi_support()
    })

@app.route('/api/wifi/connect', methods=['POST'])
def wifi_connect():
    data = request.get_json()
    ssid = data.get('ssid', '').strip()
    password = data.get('password', '').strip()
    if not ssid: return jsonify({'error': 'SSID required'}), 400
    wifi_manager.save_network(ssid, password)
    if wifi_manager.connect(ssid): return jsonify({'success': True, 'ssid': ssid})
    else: return jsonify({'error': 'Connection failed'}), 500

@app.route('/api/wifi/disconnect', methods=['POST'])
def wifi_disconnect():
    wifi_manager.disconnect()
    return jsonify({'success': True})

@app.route('/api/wifi/forget', methods=['POST'])
def wifi_forget():
    wifi_manager.forget_network()
    return jsonify({'success': True})

@app.route('/api/wifi/scan')
def wifi_scan():
    return jsonify({'networks': wifi_manager.scan()})

@app.route('/api/isos')
def api_isos():
    isos = iso_manager.list_isos()
    result =[]
    for iso in isos:
        path = iso_manager.get_iso_path(iso)
        size = os.path.getsize(path) if path and os.path.exists(path) else 0
        result.append({'name': iso, 'size': format_size(size), 'size_bytes': size})
    return jsonify(result)

@app.route('/api/delete', methods=['POST'])
def api_delete():
    filename = request.get_json().get('filename', '')
    path = iso_manager.get_iso_path(filename)
    if path and os.path.exists(path):
        os.remove(path)
        return jsonify({'success': True})
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/select', methods=['POST'])
def api_select():
    filename = request.get_json().get('filename', '')
    path = iso_manager.get_iso_path(filename)
    if path:
        try:
            import main
            if hasattr(main, 'app') and main.app:
                main.app.on_iso_selected(filename)
                return jsonify({'success': True, 'path': path})
        except: pass
    return jsonify({'error': 'Failed to select image'}), 404

@app.route('/api/disk')
def api_disk():
    total, used, free = get_disk_usage()
    return jsonify({'total': total, 'used': used, 'free': free, 'percent': int(used/total*100) if total > 0 else 0})

def format_size(bytes_size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0: return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"

def get_disk_usage():
    try:
        stat = os.statvfs(ISO_DIR)
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        used = total - free
        return total, used, free
    except: return 0, 0, 0

def start_webui(host: str = WEBUI_HOST, port: int = WEBUI_PORT, debug: bool = False):
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    logger.info(f"Starting WebUI on http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, use_reloader=False)

if __name__ == '__main__':
    start_webui()