#!/usr/bin/env python3
"""
Тестовый стенд с графиком нагрузки через Uniplot
"""

import asyncio
import random
import time
from collections import deque

from textual.app import App
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, RichLog, Static
from uniplot import plot, plot_to_string


class UniplotChart(Static):
    """Виджет графика нагрузки сети через uniplot"""

    def __init__(self, target_pps=1200, history_size=60):
        super().__init__()
        self.target_pps = target_pps
        self.history_size = history_size
        self.data = deque(maxlen=history_size)
        self.limit_data = deque(maxlen=history_size)

    def on_mount(self):
        """Запускаем обновление графика"""
        self.set_interval(1, self.update_chart)

    def add_data(self, pps: int, limit: int):
        """Добавляет новую точку данных"""
        self.data.append(pps)
        self.limit_data.append(limit)

    def update_chart(self):
        """Обновляет отображение графика"""
        if not self.data:
            self.update("📡 Ожидание данных...")
            return

        # Подготовка данных для графика
        data_list = list(self.data)
        target_line = [self.target_pps] * len(data_list)

        lines = [data_list, target_line]
        legend = ["Текущий PPS", f"Целевой PPS ({self.target_pps})"]

        # Если есть данные по лимиту, добавляем третью линию
        if self.limit_data:
            lines.append(list(self.limit_data))
            legend.append("Лимит семафора")

        # Генерируем график в виде строки
        try:
            chart = plot_to_string(
                lines,
                title="📡 ЗАГРУЗКА СЕТИ (PPS)",
                x_labels="Время (сек)",
                y_labels="Пакетов/сек",
                legend_labels=legend,
                color=True,
                width=80,
                height=15,
            )
            self.update(chart)
        except Exception as e:
            self.update(f"❌ Ошибка построения графика: {e}")


class AdaptiveSemaphoreController:
    """Адаптивный контроллер для динамического изменения лимита семафора"""

    def __init__(
        self, base_limit=50, target_pps=1200, min_limit=5, max_limit=200, inertia=0.3
    ):
        self.base_limit = base_limit
        self.target_pps = target_pps
        self.min_limit = min_limit
        self.max_limit = max_limit
        self.inertia = inertia
        self.current_limit = base_limit
        self.current_pps = 0
        self.avg_pps = 0
        self.pps_history = deque(maxlen=10)

    def get_packet_count(self):
        """Получает общее количество пакетов из /proc/net/dev"""
        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()

            total = 0
            for line in lines[2:]:
                parts = line.split()
                iface = parts[0].strip(":")
                if iface != "lo":
                    total += int(parts[2]) + int(parts[10])
            return total
        except:
            return 0

    def measure_pps(self):
        """Измеряет текущий PPS"""
        start = self.get_packet_count()
        time.sleep(1)
        end = self.get_packet_count()
        return end - start

    def update(self):
        """Обновляет метрики и рассчитывает новый лимит"""
        self.current_pps = self.measure_pps()
        self.pps_history.append(self.current_pps)
        if self.pps_history:
            self.avg_pps = sum(self.pps_history) // len(self.pps_history)
        else:
            self.avg_pps = 0

        if self.current_pps > 0:
            calculated = self.base_limit * (self.target_pps / self.current_pps)
            calculated = max(self.min_limit, min(self.max_limit, calculated))
            new_limit = (
                self.current_limit + (calculated - self.current_limit) * self.inertia
            )
            self.current_limit = round(new_limit)

        return {
            "current_pps": self.current_pps,
            "avg_pps": self.avg_pps,
            "limit": self.current_limit,
            "target": self.target_pps,
        }


class TestStandApp(App):
    """Тестовый стенд с графиком и адаптивным семафором"""

    CSS = """
    Vertical {
        height: 100%;
        background: #0a0a1a;
    }
    
    #top-panel {
        height: 25%;
        border: solid cyan;
        background: #0d0d1a;
        padding: 1;
    }
    
    #chart-container {
        height: 50%;
        border: solid green;
    }
    
    UniplotChart {
        width: 100%;
        height: 100%;
        background: #0d0d1a;
    }
    
    #log-panel {
        height: 25%;
        border: solid yellow;
        background: #0d0d1a;
        padding: 0 1;
    }
    
    Horizontal {
        height: 100%;
    }
    
    .stat-box {
        width: 33%;
        border: solid blue;
        margin: 0 1;
        padding: 0 1;
        background: #1a1a2e;
    }
    
    .stat-title {
        text-align: center;
        color: cyan;
    }
    
    .stat-value {
        text-align: center;
        color: green;
        text-style: bold;
    }
    """

    def compose(self):
        yield Header(show_clock=True)

        with Vertical():
            with Horizontal(id="top-panel"):
                with Vertical(classes="stat-box"):
                    yield Static("📦 Текущий PPS", classes="stat-title")
                    yield Static("0", id="current-pps", classes="stat-value")

                with Vertical(classes="stat-box"):
                    yield Static("📊 Средний PPS", classes="stat-title")
                    yield Static("0", id="avg-pps", classes="stat-value")

                with Vertical(classes="stat-box"):
                    yield Static("🔧 Лимит семафора", classes="stat-title")
                    yield Static("0", id="semaphore-limit", classes="stat-value")

            with Vertical(id="chart-container"):
                yield UniplotChart(target_pps=1200)

            with Vertical(id="log-panel"):
                yield RichLog(id="log")

        yield Footer()

    async def on_mount(self):
        self.controller = AdaptiveSemaphoreController()

        self.loger = self.query_one("#log", RichLog)
        self.chart = self.query_one(UniplotChart)
        self.current_pps_label = self.query_one("#current-pps", Static)
        self.avg_pps_label = self.query_one("#avg-pps", Static)
        self.limit_label = self.query_one("#semaphore-limit", Static)

        self.loger.write("🚀 Тестовый стенд запущен")
        self.loger.write("📡 Адаптивный семафор активен")
        self.loger.write(f"🎯 Целевая нагрузка: 1200 PPS")

        self.set_interval(2, self.update_statistics)
        asyncio.create_task(self.simulate_workload())

    async def update_statistics(self):
        """Обновляет статистику и график"""
        status = self.controller.update()

        self.current_pps_label.update(f"{status['current_pps']}")
        self.avg_pps_label.update(f"{status['avg_pps']}")
        self.limit_label.update(f"{status['limit']}")

        if status["current_pps"] > status["target"]:
            self.current_pps_label.styles.color = "red"
        elif status["current_pps"] > status["target"] * 0.8:
            self.current_pps_label.styles.color = "yellow"
        else:
            self.current_pps_label.styles.color = "green"

        # Добавляем данные в график
        self.chart.add_data(status["current_pps"], status["limit"])

        if status["current_pps"] > status["target"] * 1.2:
            self.loger.write(f"⚠️ Перегрузка! PPS: {status['current_pps']}")

    async def simulate_workload(self):
        """Симулирует нагрузку на сеть"""
        self.loger.write("🔄 Симулятор нагрузки запущен")

        patterns = [
            (100, 2),
            (300, 1),
            (500, 0.5),
            (200, 2),
            (50, 5),
        ]

        for workers, intensity in patterns:
            self.loger.write(f"📊 Режим: {workers} воркеров")
            for _ in range(20):
                for _ in range(workers):
                    if random.random() < intensity:
                        await asyncio.sleep(0.001)
                await asyncio.sleep(0.05)

        self.loger.write("✅ Симуляция завершена")


if __name__ == "__main__":
    app = TestStandApp()
    app.run()
