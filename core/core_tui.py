import os
import sys

from textual.app import App
from textual.containers import Horizontal, Vertical
from textual.widgets import (DataTable, Footer, ProgressBar, RichLog, Static,
                             Tab, Tabs)

# Добавляем корневую папку проекта в путь поиска модулей
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Теперь импорты
import asyncio
import traceback

from core.main_sortiring.main_sortiring_logic import MainSortiring
from core.PiplineLDS.linuxDomainSocket import linuxdomainsocket
# from core.TaskRegisterMainInit.TaskRegisterController import taskregister
from core.TaskRegisterMainInit.TaskRegister import taskregister
from worker.my import worker_http
from worker_https.my import worker_https
from worker_shadowsocks.my import worker_shadowsocks_main
from worker_socks.my import worker_socks5

#
# # === SOCKS5 источники ===
# SOCKS5_SOURCES = [
#     "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/socks5.txt",
#     "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks5.txt",
#     "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks5.txt",
#     "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
#     "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
#     "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
#     "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
#     "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
#     "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt",
#     "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
#     "https://raw.githubusercontent.com/GoekhanDev/free-proxy-list/main/socks5.txt",
#     "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/socks5.txt",
# ]
#
# # === HTTP источники ===
# HTTP_SOURCES = [
#     "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/http.txt",
#     "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt",
#     "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt",
#     "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
#     "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
#     "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
#     "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
#     "https://raw.githubusercontent.com/opsxcq/proxy-list/master/list.txt",
#     "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
#     "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
#     "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/http.txt",
#     "https://raw.githubusercontent.com/GoekhanDev/free-proxy-list/main/http.txt",
#     "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
#     "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/http.txt",
#     "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
#     "https://raw.githubusercontent.com/ALIILAPRO/Proxy/refs/heads/main/http.txt",
# ]
#
# # === HTTPS источники ===
# HTTPS_SOURCES = [
#     "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/https.txt",
#     "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/https.txt",
#     "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
#     "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
#     "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/https/data.txt",
#     "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/https/data.txt",
#     "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/https.txt",
#     "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt",
#     "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt",
#     "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
#     "https://raw.githubusercontent.com/monosans/proxy-list/refs/heads/main/proxies/https.txt",
#     "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/refs/heads/main/proxies/https.txt",
#     "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/refs/heads/master/https.txt",
#     "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/https.txt",
#     "https://raw.githubusercontent.com/roosterkid/openproxylist/refs/heads/main/HTTPS_RAW.txt",
# ]
#
# # === Mix источники (Shadowsocks, Trojan, VLESS, VMess) ===
# SOURCES_MIX = [
#     # Shadowsocks
#     "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/ss.txt",
#     "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/ss.txt",
#     "https://raw.githubusercontent.com/rileyjohngithub/free-v2ray-config/main/shadowsocks.txt",
#     "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/shadowsocks.txt",
#     "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/ss_configs.txt",
#     "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/ss.txt",
#     # "https://raw.githubusercontent.com/pourih/pfs-servers-list/refs/heads/main/pfs_servers.txt",
#     "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/1.txt",
#     "https://raw.githubusercontent.com/sevcator/5ubscrpt10n/main/protocols/ss.txt",
#     "https://raw.githubusercontent.com/ShatakVPN/ConfigForge-V2Ray/main/configs/shadowsocks.txt",
#     "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-protocol/shadowsocks.txt",
#     # Trojan
#     "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/trojan.txt",
#     "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/trojan.txt",
#     "https://raw.githubusercontent.com/rileyjohngithub/free-v2ray-config/main/trojan.txt",
#     "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/trojan.txt",
#     "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/trojan.txt",
#     # VLESS
#     "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/vless.txt",
#     "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/vless.txt",
#     "https://raw.githubusercontent.com/rileyjohngithub/free-v2ray-config/main/vless.txt",
#     "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/vless.txt",
#     # VMess
#     "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/vmess.txt",
#     "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/vmess.txt",
#     "https://raw.githubusercontent.com/rileyjohngithub/free-v2ray-config/main/vmess.txt",
#     "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/vmess.txt",
#     "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/vmess.txt",
# ]
# # В начале файла, после импортов
#
# === SOCKS5 источники (расширенные) ===
SOCKS5_SOURCES = [
    # === Ваши оригинальные источники ===
    "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/socks5.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks5.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
    "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/GoekhanDev/free-proxy-list/main/socks5.txt",
    "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/socks5.txt",
    
    # === Новые источники ===
    "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/socks5.txt",
    "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/socks5-anonymous.txt",
    "https://raw.githubusercontent.com/BlackSnowDot/proxylist-update-every-minute/main/socks5.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks5.txt",
    "https://raw.githubusercontent.com/merzehost/v2ray-collect/main/socks5.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list_raw.txt",  # Mixed, но содержит socks5
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
    "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/SOCKS5.txt",
    "https://raw.githubusercontent.com/almroot/proxylist/main/proxy_list.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/socks5/socks5.txt",
    "https://raw.githubusercontent.com/hendrikbgr/Free-Proxy-Repo/master/proxy_list.txt",
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.txt",  # Mixed
]

# === HTTP источники (расширенные) ===
HTTP_SOURCES = [
    # === Ваши оригинальные источники ===
    "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/http.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/opsxcq/proxy-list/master/list.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
    "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/http.txt",
    "https://raw.githubusercontent.com/GoekhanDev/free-proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/refs/heads/main/http.txt",
    
    # === Новые источники ===
    "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/http-anonymous.txt",
    "https://raw.githubusercontent.com/BlackSnowDot/proxylist-update-every-minute/main/http.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt",
    "https://raw.githubusercontent.com/merzehost/v2ray-collect/main/http.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/http.txt",
    "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/HTTP.txt",
    "https://raw.githubusercontent.com/almroot/proxylist/main/proxy_list.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http/http.txt",
    "https://raw.githubusercontent.com/hendrikbgr/Free-Proxy-Repo/master/proxy_list.txt",
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list_raw.txt",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
]

# === HTTPS источники (расширенные) ===
HTTPS_SOURCES = [
    # === Ваши оригинальные источники ===
    "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/https.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/https.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/https/data.txt",
    "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/https/data.txt",
    "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/https.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt",
    "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt",
    "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/refs/heads/main/proxies/https.txt",
    "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/refs/heads/main/proxies/https.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/refs/heads/master/https.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/https.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/refs/heads/main/HTTPS_RAW.txt",
    
    # === Новые источники ===
    "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/proxies/https.txt",
    "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/https.txt",
    "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/https-anonymous.txt",
    "https://raw.githubusercontent.com/BlackSnowDot/proxylist-update-every-minute/main/https.txt",
    "https://raw.githubusercontent.com/merzehost/v2ray-collect/main/https.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/https.txt",
    "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/HTTPS.txt",
    "https://raw.githubusercontent.com/almroot/proxylist/main/proxy_list.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/https/https.txt",
    "https://raw.githubusercontent.com/hendrikbgr/Free-Proxy-Repo/master/proxy_list.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list_raw.txt",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=https&timeout=10000&country=all&ssl=all&anonymity=all",
]

# === Mix источники (Shadowsocks, Trojan, VLESS, VMess) ===
SOURCES_MIX = [
    # === Ваши оригинальные источники ===
    # Shadowsocks
    "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/ss.txt",
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/ss.txt",
    "https://raw.githubusercontent.com/rileyjohngithub/free-v2ray-config/main/shadowsocks.txt",
    "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/shadowsocks.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/ss_configs.txt",
    "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/ss.txt",
    "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/1.txt",
    "https://raw.githubusercontent.com/sevcator/5ubscrpt10n/main/protocols/ss.txt",
    "https://raw.githubusercontent.com/ShatakVPN/ConfigForge-V2Ray/main/configs/shadowsocks.txt",
    "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-protocol/shadowsocks.txt",
    # Trojan
    "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/trojan.txt",
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/trojan.txt",
    "https://raw.githubusercontent.com/rileyjohngithub/free-v2ray-config/main/trojan.txt",
    "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/trojan.txt",
    "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/trojan.txt",
    # VLESS
    "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/vless.txt",
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/vless.txt",
    "https://raw.githubusercontent.com/rileyjohngithub/free-v2ray-config/main/vless.txt",
    "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/vless.txt",
    # VMess
    "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/vmess.txt",
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/vmess.txt",
    "https://raw.githubusercontent.com/rileyjohngithub/free-v2ray-config/main/vmess.txt",
    "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/vmess.txt",
    "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classes/vmess.txt",
    
    # === Новые источники ===
    # Универсальные/Все протоколы
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/all.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/all_configs.txt",
    "https://raw.githubusercontent.com/mehdirzfx/v2ray-sub/main/sub.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/all.txt",
    "https://raw.githubusercontent.com/matinghanbari/v2ray-configs/main/all.txt",
    "https://raw.githubusercontent.com/merzehost/v2ray-collect/main/subscribe.txt",
    "https://raw.githubusercontent.com/vfarid/v2ray-worker/main/worker.txt",
    "https://raw.githubusercontent.com/AzadNetCH/Clash/main/Clash.yml",
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list_raw.txt",
    
    # Shadowsocks дополнительные
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/ss.txt",
    "https://raw.githubusercontent.com/mehdirzfx/v2ray-sub/main/ss.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/ss.txt",
    "https://raw.githubusercontent.com/merzehost/v2ray-collect/main/ss.txt",
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/ss.txt",
    
    # Trojan дополнительные
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/trojan.txt",
    "https://raw.githubusercontent.com/mehdirzfx/v2ray-sub/main/trojan.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/trojan.txt",
    "https://raw.githubusercontent.com/merzehost/v2ray-collect/main/trojan.txt",
    
    # VLESS дополнительные
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/vless.txt",
    "https://raw.githubusercontent.com/mehdirzfx/v2ray-sub/main/vless.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/vless.txt",
    "https://raw.githubusercontent.com/merzehost/v2ray-collect/main/vless.txt",
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/vless.txt",
    
    # VMess дополнительные
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/vmess.txt",
    "https://raw.githubusercontent.com/mehdirzfx/v2ray-sub/main/vmess.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/vmess.txt",
    "https://raw.githubusercontent.com/merzehost/v2ray-collect/main/vmess.txt",
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/vmess.txt",
    
    # Дополнительные протоколы (Hysteria2, TUIC, Reality)
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/hysteria2.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/tuic.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/reality.txt",
    "https://raw.githubusercontent.com/merzehost/v2ray-collect/main/hysteria2.txt",
    "https://raw.githubusercontent.com/merzehost/v2ray-collect/main/tuic.txt",
]
import uuid

#
from core.adaptivDinamicSemaphore.adaptivDinamicSemaphoreDependensisWithStatsNetworkPayload import \
    AdaptiveSemaphoreController
from core.custom_widget import tui_manager
from core.tui_global_set import (get_container, reset_table,
                                 set_container_table, set_table_widget,
                                 set_widget_left, set_widget_right,
                                 set_widget_top, update_stats_avg,
                                 update_widget_right, write_left, write_right,
                                 write_test, write_top)


class ProxyCollectorApp(App):
    """TUI приложение для сбора прокси"""

    CSS = """
/* Основной контейнер */
Vertical {
    height: 100%;
    width: 100%;
    background: #0a0a1a;
}

/* Верхнее окно (логи) */
#top {
    height: 35%;
    border: solid #00ff00;
    background: #0d0d1a;
    color: #00ff00;
    padding: 0 1;
}

/* Контейнер с вкладками */
Tabs {
    height: 3;
    background: #1a1a2e;
}

Tab {
    padding: 0 2;
    background: #1a1a2e;
    color: #888;
}

Tab:focus {
    background: #00ff00;
    color: #000;
}

/* Контейнер для содержимого вкладок */
#conteiner-tabs-1 {
    height: 62%;
    width: 100%;
    overflow-y: auto;
}

#conteiner-tabs-2 {
    height: 62%;
    width: 100%;
}

/* Логи внутри первой вкладки */
#logs-tabs-1 {
    height: 20%;
    width: 100%;
    border: solid #ff4444;
    background: #0d0d1a;
    color: #ff4444;
    padding: 0 1;
}

#my-progress {
    height: 3;
    margin: 1 0;
}

/* Контейнер для динамических виджетов */
#dynamic-workers-container {
    height: auto;
    
    width: 100%;
}

/* Стили для динамических виджетов */
.dynamic-worker-container {
    height: 1;
    
    
    background: #1a1a2e;
    
}

.dynamic-worker-row {
    height: 1;
    padding-left: 3;
}

.task-name {
    width: 5%;
    color: cyan;
}

.task-stage {
    width: 10%;
    color: yellow;
}

.task-status {
    width: 4;
    color: green;
}

ProgressBar {
    height:1;
    width: 50%;
    
}

/* Горизонтальный контейнер для второй вкладки */
Horizontal {
    height: 100%;
    width: 100%;
}

/* Левое окно (статистика) */
#bottom-left {
    width: 50%;
    height: 100%;
    border: solid #4444ff;
    background: #0d0d1a;
    color: #4444ff;
    padding: 0 0;
}
/* Левое окно (статистика) вкладка 3 */
#bottom-left-tab-3 {
    width: 100%;
    height: 100%;
    border: solid #4444ff;
    background: #0d0d1a;
    color: #4444ff;
    padding: 0 0;
}
/* Правое окно (таблица) */
#stats-table {
    width: 50%;
    height: 100%;
    border: solid #ff4444;
    background: #0d0d1a;
}

/* Таблица */
DataTable {
    width: 100%;
    height: 100%;
    background: #0d0d1a;
}

DataTable:focus {
    border: solid #00ff00;
}

/* Футер */
Footer {
    background: #1a1a2e;
    border: solid #00ff00;
    color: #00ff00;
}

/* Стили для скролла */
RichLog {
    scrollbar-background: #1a1a2e;
    scrollbar-color: #00ff00;
}

.protocol-header {
    height: 1;
    color: cyan;
    text-style: bold;
    margin-top: 1;
    padding-left: 0;
}

.workers-list {
    height: auto;
    margin-left: 3;
}
.protocol-row {
    height: auto;
    width: 100%;
}

.protocol-container {
    width: 50%;
    height: auto;
    padding: 0 1;
}

/* ================================================= */
    """

    def compose(self):
        with Vertical():
            yield RichLog(id="top")

            yield Tabs(
                Tab("📊 Воркеры", id="test-1"),
                Tab("📈 Статистика", id="test-2"),
                Tab("Network AVG", id="test-3"),
            )

            with Vertical(id="conteiner-tabs-1"):
                # Первая строка - HTTP и HTTPS
                with Horizontal(classes="protocol-row"):
                    with Vertical(
                        id="dynamic-workers-container-http",
                        classes="protocol-container",
                    ):
                        yield Static("🌐 HTTP", classes="protocol-header")
                        yield Vertical(
                            id="http-workers-list", classes="workers-list"
                        )  # ← уникальный ID

                    with Vertical(id="https-container", classes="protocol-container"):
                        yield Static("🔒 HTTPS", classes="protocol-header")
                        yield Vertical(id="https-workers-list", classes="workers-list")

                # # Вторая строка - SOCKS5 и Shadowsocks
                with Horizontal(classes="protocol-row"):
                    with Vertical(id="socks5-container", classes="protocol-container"):
                        yield Static("🧦 SOCKS5", classes="protocol-header")
                        yield Vertical(id="socks5-workers-list", classes="workers-list")

                    with Vertical(
                        id="shadowsocks-container", classes="protocol-container"
                    ):
                        yield Static("🛡️ Shadowsocks", classes="protocol-header")
                        yield Vertical(
                            id="shadowsocks-workers-list", classes="workers-list"
                        )
                with Horizontal(classes="protocol-row"):
                    with Vertical(id="trojan-container", classes="protocol-container"):
                        yield Static("TROJAN", classes="protocol-header")
                        yield Vertical(id="trojan-workers-list", classes="workers-list")

                    with Vertical(id="vless-container", classes="protocol-container"):
                        yield Static("🛡️ VLESS", classes="protocol-header")
                        yield Vertical(id="vless-workers-list", classes="workers-list")

                with Horizontal(classes="protocol-row"):
                    with Vertical(id="vmess-container", classes="protocol-container"):
                        yield Static("VMESS", classes="protocol-header")
                        yield Vertical(id="vmess-workers-list", classes="workers-list")

                    with Vertical(id="none-container", classes="protocol-container"):
                        yield Static("none", classes="protocol-header")
                        yield Vertical(id="none-workers-list", classes="workers-list")

            with Vertical(id="conteiner-tabs-2"):
                with Horizontal():
                    yield RichLog(id="bottom-left")
                    yield DataTable(id="stats-table")
            with Vertical(id="conteiner-tabs-3"):
                with Horizontal():

                    yield RichLog(id="bottom-left-tab-3")

            yield Footer()

    def on_mount(self):
        # Получаем контейнеры для каждого протокола
        # reset_table()
        http_container = self.query_one("#http-workers-list", Vertical)
        https_container = self.query_one("#https-workers-list", Vertical)
        socks5_container = self.query_one("#socks5-workers-list", Vertical)
        shadowsocks_container = self.query_one("#shadowsocks-workers-list", Vertical)
        trojan_container = self.query_one("#trojan-workers-list", Vertical)
        vless_container = self.query_one("#vless-workers-list", Vertical)
        vmess_container = self.query_one("#vmess-workers-list", Vertical)

        # Регистрируем контейнеры для каждого протокола в tui_manager
        tui_manager.register_container("http", http_container)
        tui_manager.register_container("https", https_container)
        tui_manager.register_container("socks5", socks5_container)
        tui_manager.register_container("shadowsocks", shadowsocks_container)
        tui_manager.register_container("trojan", trojan_container)
        tui_manager.register_container("vless", vless_container)
        tui_manager.register_container("vmess", vmess_container)
        # Остальные виджеты
        log_top = self.query_one("#top", RichLog)
        log_left = self.query_one("#bottom-left", RichLog)
        log_right = self.query_one("#stats-table", DataTable)

        stats_avg = self.query_one("#bottom-left-tab-3", RichLog)
        set_container_table(stats_avg)

        # Устанавливаем глобальные виджеты
        set_widget_top(log_top)
        set_widget_left(log_left)
        set_table_widget(log_right)

        # Настройка вкладок
        self.container1 = self.query_one("#conteiner-tabs-1", Vertical)
        self.container2 = self.query_one("#conteiner-tabs-2", Vertical)
        self.container3 = self.query_one("#conteiner-tabs-3", Vertical)
        self.container1.display = True
        self.container2.display = False
        self.container3.display = False

        write_left("Left widget")
        write_test("Stats avg")
        self.network_controller = AdaptiveSemaphoreController(
            base_limit=50, target_pps=1200
        )
        # Запускаем коллектор
        asyncio.create_task(self.run_collector())

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        tab_id = event.tab.id
        if tab_id == "test-1":
            self.container1.display = True
            self.container2.display = False
        elif tab_id == "test-2":
            self.container1.display = False
            self.container2.display = True
        elif tab_id == "test-3":
            self.container1.display = False
            self.container2.display = False
            self.container3.display = True

    async def run_collector(self):
        """Запускает основной код сбора прокси"""

        # from core.TaskRegisterMainInit.TaskRegisterController import taskregister
        try:
            await asyncio.sleep(1)
            task_lds_server = asyncio.create_task(linuxdomainsocket.start_server_lds())
            task_main = asyncio.create_task(
                main_with_tui_interface(
                    SOCKS5_SOURCES,
                    HTTP_SOURCES,
                    HTTPS_SOURCES,
                    SOURCES_MIX,
                )
            )

            task_monitor = asyncio.create_task(
                self.network_controller.monitor_loop(callback=update_stats_avg)
            )
            await asyncio.gather(task_main, task_monitor,task_lds_server)

            # write_top("\n✅ ПРОГРАММА УСПЕШНО ЗАВЕРШЕНА")
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            tb = traceback.format_exc()

            write_top(f"\n{'='*60}")
            write_top(f"❌ ОШИБКА TUI")
            write_top(f"{'='*60}")
            write_top(f"Тип: {error_type}")
            write_top(f"Сообщение: {error_msg}")
            write_top(f"\nTraceback:\n{tb}")
            write_top(f"{'='*60}")


async def process_queue_http(queue_http, sortirovhic):
    while True:
        item = await queue_http.get()
        if "http" in item and item["http"] == None:
            write_top("found none http")
            continue
        elif "http" in item and len(item["http"]) > 1:
            write_top(f"found data for work http: {len(item['http'])} прокси")
            data = item["http"]
            data_for_sort = await soctereding(data)
            item_sort = {"http": data_for_sort}

            await sortirovhic.main_sortiring(item_sort)
        if item == "Done":
            write_top("End for working http")
            break


async def process_queue_https(queue_https, sortirovhic):
    while True:
        item = await queue_https.get()
        if "https" in item and item["https"] == None:
            write_top("found none https")
            continue
        elif "https" in item and len(item["https"]) > 1:
            write_top(f"found data for work https: {len(item['https'])} прокси")
            data = item["https"]
            data_for_sort = await soctereding(data)
            item_sort = {"https": data_for_sort}

            await sortirovhic.main_sortiring(item_sort)
        if item == "Done":
            write_top("End for working https")
            break


async def process_queue_socks(queue_sosck, sortirovhic):
    while True:
        item = await queue_sosck.get()
        if "socks" in item and item["socks"] == None:
            write_top("found none socks")
            continue
        elif "socks" in item and len(item["socks"]) > 1:
            write_top(f"found data for work socks: {len(item['socks'])} прокси")
            data = item["socks"]
            data_for_sort = await soctereding(data)
            item_sort = {"socks": data_for_sort}

            await sortirovhic.main_sortiring(item_sort)
        if item == "Done":
            write_top("End for working socks")
            break


async def process_queue_shadowsocks(queue_shadowsocks, sortirovhic):
    while True:
        item = await queue_shadowsocks.get()
        write_top(f"shadowsocks item: {str(item)[:100]}...")
        if item == "Done":
            write_top("End for working shadowsocks")
            break

        if "shadowsocks" in item and item["shadowsocks"] == None:
            write_top("found none shadowsocks")
            continue
        elif "shadowsocks" in item and len(item["shadowsocks"]) > 1:
            write_top(
                f"found data for work shadowsocks: {len(item['shadowsocks'])} прокси"
            )

            data = item["shadowsocks"]
            data_for_sort = await soctereding(data)
            item_sort = {"shadowsocks": data_for_sort}

            await sortirovhic.main_sortiring(item_sort)


async def process_queue_trojan(queue_trojan, sortirovhic):
    while True:
        item = await queue_trojan.get()
        if "trojan" in item and item["trojan"] == None:
            write_top("found none trojan")
            continue
        elif "trojan" in item and len(item["trojan"]) > 1:
            write_top(f"found data for work trojan: {len(item['trojan'])} прокси")
            data = item["trojan"]
            data_for_sort = await soctereding(data)
            item_sort = {"trojan": data_for_sort}

            await sortirovhic.main_sortiring(item_sort)
        if item == "Done":
            write_top("End for working trojan")
            break


async def process_queue_vless(queue_vless):
    while True:
        item = await queue_vless.get()

        if item == "Done":
            write_top("End for working vless")
            break

        if isinstance(item, dict) and "vless" in item:
            data = item["vless"]
            if data is not None and len(data) > 0:
                write_top(f"found data for work vless: {len(data)} прокси")
                await soctereding(data)
            else:
                write_top("found none vless")


async def process_queue_vmess(queue_vmess):
    while True:
        item = await queue_vmess.get()

        if item == "Done":
            write_top("End for working vmess")
            break

        if isinstance(item, dict) and "vmess" in item:
            data = item["vmess"]
            if data is not None and len(data) > 0:
                write_top(f"found data for work vmess: {len(data)} прокси")
                await soctereding(data)
            else:
                write_top("found none vmess")


async def main_logic_sortiring(
    queue_http,
    queue_https,
    queue_sosck,
    queue_shadowsocks,
    queue_trojan,
    queue_vless,
    queue_vmess,
    obj_main_sborhic,
):
    
    task_http = asyncio.create_task(process_queue_http(queue_http, obj_main_sborhic))
    task_https = asyncio.create_task(process_queue_https(queue_https, obj_main_sborhic))
    task_socks = asyncio.create_task(process_queue_socks(queue_sosck, obj_main_sborhic))
    task_shadowsocks = asyncio.create_task(
        process_queue_shadowsocks(queue_shadowsocks, obj_main_sborhic)
    )
    task_trojan = asyncio.create_task(
        process_queue_trojan(queue_trojan, obj_main_sborhic)
    )

    task_vless = asyncio.create_task(process_queue_vless(queue_vless))
    task_vmess = asyncio.create_task(process_queue_vmess(queue_vmess))
 
    await asyncio.gather(
        *[
            task_http,
            task_https,
            task_socks,
            task_shadowsocks,
            task_trojan,
            task_vless,
            task_vmess,
        ]
    )


async def soctereding(data):
    list_first_order = []  # 1 сервис
    list_second_order = []  # 2 сервиса
    list_third_order = []  # 3 сервиса
    list_fourth_order = []  # 4 сервиса
    list_fifth_order = []  # 5 сервисов
    list_sixth_order = []  # 6 сервисов
    combined = data
    if isinstance(data, dict):
        write_top(f"Получен словарь с ключами: {list(data.keys())}")

        # 2. Проверяем, есть ли обёртка протокола
        for protocol in [
            "shadowsocks",
            "trojan",
            "vless",
            "vmess",
            "http",
            "https",
            "socks",
        ]:
            if protocol in data:
                write_top(f"Найдена обёртка протокола: {protocol}")
                data = data[protocol]  # Извлекаем внутренние данные
                break

        if isinstance(data, dict):
            write_top("Преобразуем словарь в список для обработки")
            combined = [data]

    for item in combined:
        if "host:port:type" in item and item["host:port:type"]:
            proxy_url = item.get("host:port:type")

            # proxy_url = item["host:port:type"]
        elif "proxy_url" in item and item["proxy_url"]:
            proxy_url = item.get("proxy_url")

        # proxy_url = item.get("host:port:type")

        # Считаем количество работающих сервисов
        services_status = [
            ("telegram", item.get("telegram")),
            ("instagram", item.get("instagram")),
            ("youtube", item.get("youtube")),
            ("facebook", item.get("facebook")),
            ("rutracker", item.get("rutracker")),
            ("zoomeye", item.get("zoomeye")),
        ]

        # Подсчёт работающих сервисов
        working_services = [
            (name, status) for name, status in services_status if status
        ]
        count = len(working_services)

        if count > 0:
            proxy_info = {
                "proxy": proxy_url,
                "working_services": working_services,
                "count": count,
            }

            # Сортируем по количеству
            if count == 1:
                list_first_order.append(proxy_info)
            elif count == 2:
                list_second_order.append(proxy_info)
            elif count == 3:
                list_third_order.append(proxy_info)
            elif count == 4:
                list_fourth_order.append(proxy_info)
            elif count == 5:
                list_fifth_order.append(proxy_info)
            elif count == 6:
                list_sixth_order.append(proxy_info)

    # Вывод статистики
    write_left("\n" + "=" * 60)
    write_left("📊 СОРТИРОВКА ПРОКСИ ПО ПОРЯДКУ")
    write_left("=" * 60)
    write_left(f"🎯 1 порядок (1 сервис):  {len(list_first_order)} прокси")
    write_left(f"🎯 2 порядок (2 сервиса): {len(list_second_order)} прокси")
    write_left(f"🎯 3 порядок (3 сервиса): {len(list_third_order)} прокси")
    write_left(f"🎯 4 порядок (4 сервиса): {len(list_fourth_order)} прокси")
    write_left(f"🎯 5 порядок (5 сервисов): {len(list_fifth_order)} прокси")
    write_left(f"🎯 6 порядок (6 сервисов): {len(list_sixth_order)} прокси")
    write_left("=" * 60)
    #
    return {
        "1": list_first_order,
        "2": list_second_order,
        "3": list_third_order,
        "4": list_fourth_order,
        "5": list_fifth_order,
        "6": list_sixth_order,
    }


import uuid

from core.custom_widget import register_task, update_task


async def main_with_tui_interface(
    SOCKS5_SOURCES, HTTP_SOURCES, HTTPS_SOURCES, SS_SOURCES_MIX
):
    queue_http = asyncio.Queue()
    queue_https = asyncio.Queue()
    queue_sosck = asyncio.Queue()
    queue_shadowsocks = asyncio.Queue()
    queue_trojan = asyncio.Queue()
    queue_vless = asyncio.Queue()
    queue_vmess = asyncio.Queue()
    main_sortiring = MainSortiring(
        queue_http,
        queue_https,
        queue_sosck,
        queue_shadowsocks,
        queue_trojan,
        queue_vless,
        queue_vmess,
    )
    write_top("📥 Запуск воркеров...")

    GLOBAL_REQUEST_SEMAPHORE_HTTP = 350 
    GLOBAL_REQUEST_SEMAPHORE_HTTPS = 350 
    GLOBAL_REQUEST_SEMAPHORE_SOCKS5 = 250
    GLOBAL_REQUEST_SEMAPHORE_SHADOWSOCKS = 100
    task_so = asyncio.create_task(
          worker_socks5(SOCKS5_SOURCES, queue_sosck, GLOBAL_REQUEST_SEMAPHORE_SOCKS5)
    )
    task_http = asyncio.create_task(
         worker_http(HTTP_SOURCES, queue_http, GLOBAL_REQUEST_SEMAPHORE_HTTP)
    )
    task_https = asyncio.create_task(
          worker_https(HTTPS_SOURCES, queue_https, GLOBAL_REQUEST_SEMAPHORE_HTTPS)
    )
    # task_shadowsocks = asyncio.create_task(
    #      worker_shadowsocks_main(
    #          SS_SOURCES_MIX,
    #          queue_shadowsocks,
    #          queue_trojan,
    #          queue_vless,
    #          queue_vmess,
    #          GLOBAL_REQUEST_SEMAPHORE_SHADOWSOCKS,
    #      )
    #  )

    task_sortering = asyncio.create_task(
        main_logic_sortiring(
            queue_http,
            queue_https,
            queue_sosck,
            queue_shadowsocks,
            queue_trojan,
            queue_vless,
            queue_vmess,
            main_sortiring,
        )
    )

    write_top("🔄 Ожидание завершения всех задач...")

    await asyncio.gather(
        task_http,
        task_https,
        task_so,
        #task_shadowsocks,
        task_sortering,
    )
