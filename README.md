# burp_suite
HTTP Proxy GUI for request interception

Python 3 + PyQt5 HTTP Proxy GUI  
With real-time request interception, forwarding, dropping, replay, filtering and highlighting functions.

---

## 📌 Features

- HTTP request capture (GET, POST)  
- Forward / Drop / Replay requests  
- Filter by method, status, or keyword  
- Highlight sensitive keywords (password, token, session)  
- Export captured requests to JSON  
- Clear all captured requests  
- PyQt5 GUI  

---

## ⚙️ Installation

1. Python 3.11+ must be installed 
2. Install PyQt5:

```bash
pip install PyQt5
Clone the project from GitHub:
https://github.com/quliyev-sahin/burp_suite.git

🚀 Usage

python burpsuite4.py

Configure your browser as an HTTP proxy for 127.0.0.1:8888

![Main Screenshot](https://raw.githubusercontent.com/quliyev-sahin/burp_suite/main/images/1.png)


GUI-də bütün HTTP requestlər görünəcək

Requesti seçərək Forward / Drop / Replay edə bilərsən

Filter və search ilə requestləri axtara bilərsən

🖼 Screenshots
(Buraya toolun ekran görüntülərini əlavə et)

📝 Export Requests
Captured requestləri JSON formatında export etmək mümkündür.

Exported JSON struktur nümunəsi:

json
Kopyala
Düzenle
[
  {
    "id": 0,
    "method": "GET",
    "path": "/test.php",
    "status": "Completed",
    "headers": {
      "Host": "localhost",
      "User-Agent": "Mozilla/5.0"
    },
    "body": ""
  }
]    
