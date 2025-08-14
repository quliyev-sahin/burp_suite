#!/usr/bin/env python3
import sys, threading, socket, select, queue, time, json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QSplitter, QVBoxLayout, QWidget, QPushButton,
    QLineEdit, QLabel, QFileDialog, QComboBox,
    QHBoxLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor

# ----------------- Proxy parametrləri -----------------
PORT = 8888
MAX_ENTRIES = 500
request_queue = queue.Queue()
captured = []
lock = threading.Lock()
HIGHLIGHT_KEYWORDS = ["password", "token", "session"]

# ----------------- Request Entry -----------------
class RequestEntry:
    _id_counter = 0
    def __init__(self, client_socket, raw_request):
        self.id = RequestEntry._id_counter
        RequestEntry._id_counter += 1
        self.client_socket = client_socket
        self.raw_request = raw_request
        self.status = "Pending"
        self.method = ""
        self.path = ""
        self.headers = {}
        self.body = b""
        self.processed = False
        self.tree_item = None
        self.parse_request()

    def parse_request(self):
        try:
            lines = self.raw_request.split(b"\r\n")
            request_line = lines[0].decode()
            parts = request_line.split()
            if len(parts) >= 2:
                self.method = parts[0]
                self.path = parts[1]
            i = 1
            while i < len(lines) and lines[i]:
                if b":" in lines[i]:
                    k, v = lines[i].decode().split(":",1)
                    self.headers[k.strip()] = v.strip()
                i += 1
            self.body = b"\r\n".join(lines[i+1:])
        except:
            pass

# ----------------- Proxy funksiyaları -----------------
def handle_client(client_socket, gui_signal):
    try:
        while True:
            data = client_socket.recv(65535)
            if not data:
                break
            entry = RequestEntry(client_socket, data)
            request_queue.put(entry)
            with lock:
                captured.append(entry)
                if len(captured) > MAX_ENTRIES:
                    captured.pop(0)
            gui_signal.emit()
    except Exception:
        pass
    finally:
        try:
            client_socket.close()
        except:
            pass

def proxy_server(gui_signal):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("", PORT))
    server.listen(100)
    print(f"[*] HTTP Proxy running on port {PORT}")
    while True:
        rlist, _, _ = select.select([server], [], [], 0.5)
        for s in rlist:
            client_socket, addr = server.accept()
            threading.Thread(target=handle_client, args=(client_socket, gui_signal), daemon=True).start()

def forward_socket(entry, modified_request=None):
    if entry.processed:
        return
    entry.processed = True
    entry.status = "Forwarding"
    if entry.tree_item:
        entry.tree_item.setText(3, entry.status)
    threading.Thread(target=_forward_thread, args=(entry, modified_request), daemon=True).start()

def _forward_thread(entry, modified_request=None):
    try:
        request_to_send = modified_request if modified_request else entry.raw_request
        host_header = entry.headers.get("Host","")
        if not host_header:
            entry.status = "Error: No Host header"
            if entry.tree_item:
                entry.tree_item.setText(3, entry.status)
            return

        host = host_header
        port = 80
        if ":" in host:
            host, port = host.split(":")
            port = int(port)

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect((host, port))
        server_socket.sendall(request_to_send)

        while True:
            data = server_socket.recv(65535)
            if not data:
                break
            try:
                entry.client_socket.sendall(data)
            except OSError:
                break

        server_socket.close()
        try:
            entry.client_socket.close()
        except:
            pass
        entry.status = "Completed"
    except Exception as e:
        entry.status = f"Error: {e}"
        try:
            entry.client_socket.close()
        except:
            pass
    finally:
        if entry.tree_item:
            entry.tree_item.setText(3, entry.status)

def drop_socket(entry):
    if entry.processed:
        return
    entry.processed = True
    entry.status = "Dropping"
    if entry.tree_item:
        entry.tree_item.setText(3, entry.status)
    threading.Thread(target=_drop_thread, args=(entry,), daemon=True).start()

def _drop_thread(entry):
    try:
        entry.client_socket.sendall(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\nRequest Dropped")
        entry.client_socket.close()
        entry.status = "Dropped"
    except:
        pass
    finally:
        if entry.tree_item:
            entry.tree_item.setText(3, entry.status)

# ----------------- GUI -----------------
class SignalEmitter(QObject):
    refresh_signal = pyqtSignal()

class ProxyGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HTTP Proxy GUI (Burp-like)")
        self.setGeometry(50, 50, 1600, 900)
        splitter = QSplitter(Qt.Horizontal)

        # -------- Left panel --------
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Filter requests...")
        self.search_bar.textChanged.connect(self.apply_filter)
        left_layout.addWidget(QLabel("Filter Requests:"))
        left_layout.addWidget(self.search_bar)

        self.method_filter = QComboBox()
        self.method_filter.addItems(["All","GET","POST","PUT","DELETE"])
        self.method_filter.currentIndexChanged.connect(self.apply_filter)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All","Pending","Forwarding","Completed","Dropped","Error"])
        self.status_filter.currentIndexChanged.connect(self.apply_filter)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel("Method:"))
        hlayout.addWidget(self.method_filter)
        hlayout.addWidget(QLabel("Status:"))
        hlayout.addWidget(self.status_filter)
        left_layout.addLayout(hlayout)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["ID","Method","Path","Status"])
        self.tree.itemClicked.connect(self.display_details)
        left_layout.addWidget(self.tree)

        toolbar_layout = QHBoxLayout()
        self.export_btn = QPushButton("Export JSON")
        self.export_btn.clicked.connect(self.export_json)
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.clear_all)
        toolbar_layout.addWidget(self.export_btn)
        toolbar_layout.addWidget(self.clear_btn)
        left_layout.addLayout(toolbar_layout)

        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)

        # -------- Right panel --------
        right_widget = QWidget()
        vlayout = QVBoxLayout()
        self.detail = QTextEdit()
        self.detail.setFont(QFont("Courier New",10))
        vlayout.addWidget(QLabel("Request Editor:"))
        vlayout.addWidget(self.detail)

        btn_layout = QHBoxLayout()
        self.forward_btn = QPushButton("Forward")
        self.forward_btn.clicked.connect(self.forward_request)
        self.drop_btn = QPushButton("Drop")
        self.drop_btn.clicked.connect(self.drop_request)
        self.replay_btn = QPushButton("Replay")
        self.replay_btn.clicked.connect(self.replay_request)
        btn_layout.addWidget(self.forward_btn)
        btn_layout.addWidget(self.drop_btn)
        btn_layout.addWidget(self.replay_btn)
        vlayout.addLayout(btn_layout)

        self.response_viewer = QTextEdit()
        self.response_viewer.setFont(QFont("Courier New",10))
        self.response_viewer.setReadOnly(True)
        vlayout.addWidget(QLabel("Response Viewer:"))
        vlayout.addWidget(self.response_viewer)

        right_widget.setLayout(vlayout)
        splitter.addWidget(right_widget)
        splitter.setSizes([700,900])
        self.setCentralWidget(splitter)

        self.selected_entry = None
        self.signals = SignalEmitter()
        self.signals.refresh_signal.connect(self.refresh_tree)

        threading.Thread(target=self.background_refresh, daemon=True).start()
        threading.Thread(target=self.queue_processor, daemon=True).start()
        threading.Thread(target=proxy_server, args=(self.signals.refresh_signal,), daemon=True).start()

    # ----------------- GUI metodları -----------------
    def apply_filter(self):
        method = self.method_filter.currentText() if hasattr(self,'method_filter') else "All"
        status = self.status_filter.currentText() if hasattr(self,'status_filter') else "All"
        keyword = self.search_bar.text().lower() if hasattr(self,'search_bar') else ""
        with lock:
            for entry in captured:
                if entry.tree_item:
                    text = f"{entry.method} {entry.path} {entry.status}".lower()
                    match = True
                    if method != "All" and entry.method != method:
                        match = False
                    if status != "All" and not entry.status.startswith(status):
                        match = False
                    if keyword and keyword not in text:
                        match = False
                    entry.tree_item.setHidden(not match)
                    # Highlight keywords
                    for kw in HIGHLIGHT_KEYWORDS:
                        if kw in text:
                            for col in range(4):
                                entry.tree_item.setForeground(col, QColor("red"))

    def refresh_tree(self):
        with lock:
            for entry in captured:
                if not entry.tree_item:
                    item = QTreeWidgetItem([str(entry.id), entry.method, entry.path, entry.status])
                    item.setData(0, Qt.UserRole, entry)
                    self.tree.addTopLevelItem(item)
                    entry.tree_item = item
                else:
                    entry.tree_item.setText(3, entry.status)

    def display_details(self, item, column):
        entry = item.data(0, Qt.UserRole)
        if entry:
            self.selected_entry = entry
            self.detail.setText(entry.raw_request.decode(errors='ignore'))

    def forward_request(self):
        if self.selected_entry:
            modified_request = self.detail.toPlainText().encode()
            forward_socket(self.selected_entry, modified_request)

    def drop_request(self):
        if self.selected_entry:
            drop_socket(self.selected_entry)

    def replay_request(self):
        if self.selected_entry:
            forward_socket(self.selected_entry, self.selected_entry.raw_request)

    def export_json(self):
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getSaveFileName(self,"Save JSON","requests.json","JSON Files (*.json)", options=options)
        if filename:
            data = []
            with lock:
                for entry in captured:
                    data.append({
                        "id": entry.id,
                        "method": entry.method,
                        "path": entry.path,
                        "status": entry.status,
                        "headers": entry.headers,
                        "body": entry.body.decode(errors='ignore')
                    })
            with open(filename,"w") as f:
                json.dump(data, f, indent=2)

    def clear_all(self):
        with lock:
            captured.clear()
            self.tree.clear()
            self.detail.clear()
            self.response_viewer.clear()

    def background_refresh(self):
        while True:
            time.sleep(0.2)
            self.signals.refresh_signal.emit()

    def queue_processor(self):
        while True:
            entry = request_queue.get()
            self.signals.refresh_signal.emit()
            self.selected_entry = entry

# ----------------- Main -----------------
if __name__=="__main__":
    app = QApplication(sys.argv)
    window = ProxyGUI()
    window.show()
    sys.exit(app.exec_())
