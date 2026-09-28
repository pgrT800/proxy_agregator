import asyncio
import json
import os

from core.tui_global_set import write_top


class LinuxDomainSocket:
    def __init__(self) -> None:
        self.path_socket_brain_patch = "/tmp/my_socket_for_server.sock"
        self.http_pool = {}  # {"1": [...], "2": [...], ...}
        self.https_pool = {}
        self.socks5_pool = {}
        self.shadowsocks_pool = {}
        self.trojan_pool = {}
        self.vless_pool = {}
        self.vmess_pool = {}

    async def server_data(self, protocol: str, data: dict):
        """Сохраняет данные по протоколу"""
        pools = {
            "http": "http_pool",
            "https": "https_pool",
            "socks5": "socks5_pool",
            "shadowsocks": "shadowsocks_pool",
            "trojan": "trojan_pool",
            "vless": "vless_pool",
            "vmess": "vmess_pool",
        }
        if protocol in pools:
            setattr(self, pools[protocol], data)

    async def handler_server(self, reader, writer):
        peername = writer.get_extra_info("peername")
        write_top(f"📡 Подключился клиент: {peername}")

        try:
            data = await reader.read(1024)
            if data:
                message = data.decode()
                write_top(f"📥 Получено: {message}")

                if message == "all":
                    response = json.dumps(
                        {
                            "http": self.http_pool,
                            "https": self.https_pool,
                            "socks5": self.socks5_pool,
                            "shadowsocks": self.shadowsocks_pool,
                            "trojan": self.trojan_pool,
                            "vless": self.vless_pool,
                            "vmess": self.vmess_pool,
                        }
                    )
                elif message.startswith("proxy:"):
                    # proxy:http, proxy:https, proxy:socks5, ...
                    _, protocol = message.split(":", 1)
                    pools = {
                        "http": self.http_pool,
                        "https": self.https_pool,
                        "socks5": self.socks5_pool,
                        "shadowsocks": self.shadowsocks_pool,
                        "trojan": self.trojan_pool,
                        "vless": self.vless_pool,
                        "vmess": self.vmess_pool,
                    }
                    response = json.dumps(pools.get(protocol, {}))
                elif message == "ping":
                    response = "pong"
                else:
                    response = "UNKNOWN"

                writer.write(response.encode())
                await writer.drain()

        except ConnectionResetError:
            write_top(f"🔌 {peername}: соединение разорвано")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start_server_lds(self):
        if os.path.exists(self.path_socket_brain_patch):
            os.unlink(self.path_socket_brain_patch)

        server = await asyncio.start_unix_server(
            self.handler_server, path=self.path_socket_brain_patch
        )
        write_top(f"🎧 LDS сервер запущен: {self.path_socket_brain_patch}")

        async with server:
            await server.serve_forever()


linuxdomainsocket = LinuxDomainSocket()
