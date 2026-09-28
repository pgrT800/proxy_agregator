import socket

from flask import Flask, render_template_string, request

app = Flask(__name__)

DEFAULT_FILE = (
    "/home/admin/programmer-project/pythonProject/proxy_generate/alive_proxies_tg.txt"
)


def read_file_lines(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return None


def get_local_ip():
    """Получает локальный IP адрес компьютера в сети"""
    try:
        # Создаем временное соединение чтобы узнать наш IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@app.route("/")
def index():
    filename = request.args.get("file", DEFAULT_FILE)
    lines = read_file_lines(filename)

    if lines is None:
        return f"Файл '{filename}' не найден", 404

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ссылки из {{ filename }}</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: monospace; margin: 30px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
            .link-item { margin: 12px 0; padding: 8px; background: #f9f9f9; border-radius: 5px; }
            a { color: #0366d6; text-decoration: none; word-break: break-all; }
            a:hover { text-decoration: underline; }
            .info { color: #666; margin-bottom: 20px; padding: 10px; background: #e8f4f8; border-radius: 5px; }
            h2 { color: #333; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>📄 Файл: {{ filename }}</h2>
            <div class="info">✅ Всего строк: {{ lines|length }}</div>
            {% for line in lines %}
                <div class="link-item">
                    🔗 <a href="{{ line }}" target="_blank">{{ line }}</a>
                </div>
            {% endfor %}
        </div>
    </body>
    </html>
    """
    return render_template_string(html, lines=lines, filename=filename)


if __name__ == "__main__":
    local_ip = get_local_ip()
    print("=" * 50)
    print(f"🚀 Сервер запущен!")
    print(f"📱 С телефона заходите по адресу: http://{local_ip}:5000")
    print(f"💻 С компьютера: http://127.0.0.1:5000")
    print("=" * 50)
    print("⚠️  Убедитесь что телефон в той же Wi-Fi сети что и компьютер")
    print("⚠️  И проверьте что файл links.txt существует в папке со скриптом")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)
