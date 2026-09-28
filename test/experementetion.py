import asyncio
import random

from textual.app import App, ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, ProgressBar, RichLog, Static


class WorkerWidget(Static):
    """Виджет для отдельного воркера с прогресс-баром и статусом"""

    def __init__(self, name: str, stages: list):
        super().__init__()
        self.worker_name = name
        self.worker_id = name.replace(" ", "-").lower()  # HTTP Worker -> http-worker
        self.stages = stages  # ["get_data", "checker", "validate"]
        self.current_stage = 0
        self.current_progress = 0
        self.total_items = 0
        self.processed_items = 0
        self.status = "waiting"  # waiting, running, done, error

    def compose(self):
        with Vertical(classes="worker-container"):
            # Всё в одной строке
            with Horizontal(classes="worker-row"):
                yield Static(
                    f"🤖 {self.worker_name}",
                    id=f"worker-name-{self.worker_id}",
                    classes="worker-name",
                )
                yield Static("", id=f"stage-{self.worker_id}", classes="stage-label")
                yield ProgressBar(
                    total=100,
                    show_percentage=True,
                    id=f"progress-{self.worker_id}",
                    classes="worker-progress",
                )
                yield Static("", id=f"status-{self.worker_id}", classes="status-label")

            # Информационная строка (компактная)
            with Horizontal(classes="info-row"):
                yield Static("", id=f"info-{self.worker_id}", classes="info-text")

    def set_total(self, total: int):
        """Устанавливает общее количество элементов для обработки"""
        self.total_items = total
        self.processed_items = 0
        self.update_progress(0)

    def next_stage(self):
        """Переход на следующую стадию"""
        self.current_stage += 1
        self.current_progress = 0
        self.processed_items = 0
        self.update_progress(0)

        if self.current_stage < len(self.stages):
            self.set_stage(self.stages[self.current_stage])

    def set_stage(self, stage: str):
        """Устанавливает текущую стадию"""
        stage_names = {
            "get_data": "📥 Получение",
            "checker": "🔍 Проверка",
            "validate": "✅ Валидация",
        }
        stage_text = stage_names.get(stage, stage)
        self.query_one(f"#stage-{self.worker_id}", Static).update(stage_text)

    def update_progress(self, value: int, status: str = None):
        """Обновляет прогресс и статус"""
        self.current_progress = value
        progress = self.query_one(f"#progress-{self.worker_id}", ProgressBar)

        if self.total_items > 0:
            percent = int((self.processed_items / self.total_items) * 100)
            progress.update(progress=percent)
        else:
            progress.update(progress=value)

        if status:
            self.status = status
            status_widget = self.query_one(f"#status-{self.worker_id}", Static)
            status_colors = {
                "waiting": "⏳",
                "running": "🔄",
                "done": "✅",
                "error": "❌",
            }
            status_widget.update(status_colors.get(status, status))

    def add_processed(self, count: int = 1):
        """Увеличивает счётчик обработанных элементов"""
        self.processed_items += count
        if self.total_items > 0:
            percent = int((self.processed_items / self.total_items) * 100)
            self.update_progress(percent)

    def set_info(self, text: str):
        """Устанавливает дополнительную информацию"""
        self.query_one(f"#info-{self.worker_id}", Static).update(text)

    def set_done(self):
        """Отмечает воркер как завершённый"""
        self.status = "done"
        self.update_progress(100, "done")
        self.set_info("✅ Работа завершена")


class WorkerTestApp(App):
    """Тестовое приложение для динамических воркеров"""

    CSS = """
   Vertical {
    height: 100%;
    background: #0a0a1a;
}

#log-panel {
    height: 30%;
    border: solid green;
    background: #0d0d1a;
    color: #00ff00;
    padding: 0 1;
}

#workers-container {
    height: 70%;
    border: solid yellow;
    background: #0a0a1a;
}

#workers-scroll {
    height: 100%;
}

/* Максимально компактный контейнер воркера */
.worker-container {
    height: 1;           /* Минимальная высота */
    border: none;        /* Убираем рамку */
    margin: 0;           /* Убираем отступы */
    background: #1a1a2e;
    padding: 0;
}

/* Строка воркера - минимальная высота */
.worker-row {
    height: 1;
    align: center middle;
}

/* Имя воркера - минимальная ширина */
.worker-name {
    width: 10;
    color: cyan;
}

/* Стадия работы - минимальная ширина */
.stage-label {
    width: 10;
    color: yellow;
}

/* Прогресс-бар - компактный */
.worker-progress {
    width: 30%;
    margin: 0;
}

/* Статус - минимальная ширина */
.status-label {
    width: 2;
    color: green;
}

/* Скрытая информационная строка */
.info-row {
    height: 0;
    display: none;
}

.info-text {
    color: gray;
}

ProgressBar {
    margin: 0;
    height: 1;           /* Минимальная высота прогресс-бара */
} 
    """

    def compose(self):
        yield Header(show_clock=True)

        with Vertical():
            yield RichLog(id="log-panel")

            with Vertical(id="workers-container"):
                with ScrollableContainer(id="workers-scroll"):
                    yield Vertical(id="workers-list")

        yield Footer()

    def on_mount(self):
        self.loger = self.query_one("#log-panel", RichLog)
        self.workers_list = self.query_one("#workers-list", Vertical)
        self.worker_items = []

        self.loger.write("🚀 Тестовый стенд запущен")
        self.loger.write("=" * 50)

        # Создаём воркеров
        asyncio.create_task(self.create_workers())

    async def create_workers(self):
        """Создаёт воркеров динамически"""
        worker_configs = [
            {"name": "HTTP-Worker", "stages": ["get_data", "checker", "validate"]},
            {"name": "SOCKS5-Worker", "stages": ["get_data", "checker", "validate"]},
            {"name": "HTTPS-Worker", "stages": ["get_data", "checker", "validate"]},
            {"name": "HTTPS-Worker", "stages": ["get_data", "checker", "validate"]},
            {"name": "HTTPS-Worker", "stages": ["get_data", "checker", "validate"]},
        ]

        for config in worker_configs:
            worker = WorkerWidget(config["name"], config["stages"])
            await self.workers_list.mount(worker)
            self.worker_items.append(worker)
            self.loger.write(f"➕ Добавлен воркер: {config['name']}")
            await asyncio.sleep(0.3)

        self.loger.write(f"✅ Всего создано воркеров: {len(self.worker_items)}")

        # Запускаем всех воркеров
        await self.run_all_workers()

    async def run_all_workers(self):
        """Запускает всех воркеров параллельно"""
        tasks = []
        for i, worker in enumerate(self.worker_items):
            tasks.append(self.run_worker(worker, i))

        await asyncio.gather(*tasks)
        self.loger.write("🎉 Все воркеры завершили работу!")

    async def run_worker(self, worker: WorkerWidget, worker_id: int):
        """Симуляция работы воркера"""
        worker_name = worker.worker_name

        # Стадия 1: Получение данных
        worker.set_stage("get_data")
        worker.update_progress(0, "running")

        total_items = random.randint(50, 200)
        worker.set_total(total_items)
        worker.set_info(f"{total_items} эл.")
        self.loger.write(f"📥 {worker_name}: получение {total_items} элементов")

        for i in range(total_items):
            worker.add_processed(1)
            if i % 20 == 0:
                worker.set_info(f"{i+1}/{total_items}")
            await asyncio.sleep(0.01)

        worker.set_info(f"✅ {total_items}")
        self.loger.write(f"✅ {worker_name}: загружено {total_items} элементов")
        await asyncio.sleep(0.5)

        # Стадия 2: Проверка
        worker.next_stage()
        worker.set_stage("checker")
        worker.update_progress(0)
        worker.set_info(f"0/{total_items}")

        checked = 0
        good_count = 0
        for i in range(total_items):
            checked += 1
            if random.random() > 0.3:
                good_count += 1
            worker.add_processed(1)
            if i % 20 == 0:
                worker.set_info(f"{checked}/{total_items} ✅{good_count}")
            await asyncio.sleep(0.01)

        worker.set_info(f"✅ {good_count}/{total_items}")
        self.loger.write(
            f"✅ {worker_name}: проверка завершена ({good_count}/{total_items})"
        )
        await asyncio.sleep(0.5)

        # Стадия 3: Валидация
        worker.next_stage()
        worker.set_stage("validate")
        worker.update_progress(0)
        worker.set_info(f"0/{good_count}")

        validated = 0
        for i in range(good_count):
            validated += 1
            percent = int((validated / good_count) * 100) if good_count > 0 else 100
            worker.update_progress(percent)
            if i % 10 == 0:
                worker.set_info(f"{validated}/{good_count} ({percent}%)")
            await asyncio.sleep(0.01)

        worker.set_info(f"✅ {validated}/{good_count}")
        self.loger.write(
            f"✅ {worker_name}: валидация завершена ({validated}/{good_count})"
        )

        # Завершение работы
        worker.set_done()
        worker.set_info("✅ Готов")
        self.loger.write(f"🏁 {worker_name}: работа завершена!")


if __name__ == "__main__":
    app = WorkerTestApp()
    app.run()

# from textual.app import App, ComposeResult
# from textual.containers import Horizontal, Vertical
# from textual.widgets import DataTable, Footer, Header, RichLog, Static, Tab, Tabs
#
#
# class SimpleTabsApp(App):
#     def compose(self) -> ComposeResult:
#         yield Header(show_clock=True)
#
#         with Vertical():
#             # Верхнее окно (общее)
#             yield RichLog(id="top")
#
#             # Вкладки
#             yield Tabs(
#                 Tab("📊 Вкладка 1", id="tab-1"),
#                 Tab("📝 Вкладка 2", id="tab-2"),
#             )
#
#             # Контейнер для Вкладки 1
#             with Vertical(id="container-1"):
#                 with Horizontal():
#                     yield RichLog(id="log-1")
#                     yield RichLog(id="log-3")
#             # Контейнер для Вкладки 2
#             with Vertical(id="container-2"):
#                 yield RichLog(id="log-2")
#
#         yield Footer()
#
#     def on_mount(self) -> None:
#         self.conteiner1 = self.query_one("#container-1", Vertical)
#         self.conteiner2 = self.query_one("#container-2", Vertical)
#
#         self.top = self.query_one("#top", RichLog)
#         self.top.write("nigga")
#
#         self.tab1 = self.query_one("#log-1", RichLog)
#         self.tab1.write("tab1")
#
#         self.tab2 = self.query_one("#log-2", RichLog)
#         self.tab2.write("tabs2")
#
#         self.tab3 = self.query_one("#log-3", RichLog)
#         self.tab3.write("tabs3")
#         self.conteiner1.display = True
#         self.conteiner2.display = False
#
#     def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
#         tab_id = event.tab.id
#         container1 = self.conteiner1
#         container2 = self.conteiner2
#         if tab_id == "tab-1":
#             container1.display = True
#             container2.display = False
#         elif tab_id == "tab-2":
#             container1.display = False
#             container2.display = True
#
#
# if __name__ == "__main__":
#     app = SimpleTabsApp()
#     app.run()
# #!/usr/bin/env python3
# """
# TUI скрипт - пример с вкладками (Tabs)
# """
#
# import asyncio
#
# from textual.app import App
# from textual.containers import Horizontal, ScrollableContainer, Vertical
# from textual.widgets import Footer, Header, RichLog, Static, Tab, Tabs
#
#
# class TabbedApp(App):
#     """Приложение с вкладками"""
#
#     CSS = """
#     Vertical {
#         height: 100%;
#     }
#
#     Tabs {
#         height: 3;
#         background: $surface;
#     }
#
#     .tab-content {
#         height: 100%;
#     }
#
#     RichLog {
#         border: solid cyan;
#         background: #1a1a2e;
#     }
#     """
#
#     def compose(self):
#         yield Header(show_clock=True)
#
#         with Vertical():
#             # Вкладки
#             yield Tabs(
#                 Tab("📊 Логи", id="tab-logs"),
#                 Tab("📈 Статистика", id="tab-stats"),
#                 Tab("🔧 Настройки", id="tab-settings"),
#                 Tab("ℹ️ О программе", id="tab-about"),
#             )
#
#             # Контейнеры для содержимого вкладок
#             with Vertical(id="content-logs", classes="tab-content"):
#                 yield RichLog(id="logs-panel")
#
#             with Vertical(id="content-stats", classes="tab-content"):
#                 yield Static("Статистика пока не собрана...", id="stats-panel")
#
#             with Vertical(id="content-settings", classes="tab-content"):
#                 yield Static(
#                     "Настройки:\n\n- Лимит подключений: 100\n- Таймаут: 7 сек",
#                     id="settings-panel",
#                 )
#
#             with Vertical(id="content-about", classes="tab-content"):
#                 yield Static(
#                     "Proxy Collector v1.0\n\nСобирает и проверяет прокси",
#                     id="about-panel",
#                 )
#
#         yield Footer()
#
#     def on_mount(self):
#         # Показываем первую вкладку по умолчанию
#         self.query_one(Tabs).active = "tab-logs"
#         self.show_tab("logs")
#
#         self.logs = self.query_one("#logs-panel", RichLog)
#         self.logs.write("🚀 Программа запущена")
#
#         asyncio.create_task(self.demo_worker())
#
#     def on_tabs_tab_activated(self, event: Tabs.TabActivated):
#         """Обработчик переключения вкладок"""
#         tab_id = event.tab.id
#
#         # Скрываем все контейнеры
#         self.query_one("#content-logs", Vertical).display = False
#         self.query_one("#content-stats", Vertical).display = False
#         self.query_one("#content-settings", Vertical).display = False
#         self.query_one("#content-about", Vertical).display = False
#
#         # Показываем выбранный
#         if tab_id == "tab-logs":
#             self.query_one("#content-logs", Vertical).display = True
#         elif tab_id == "tab-stats":
#             self.query_one("#content-stats", Vertical).display = True
#         elif tab_id == "tab-settings":
#             self.query_one("#content-settings", Vertical).display = True
#         elif tab_id == "tab-about":
#             self.query_one("#content-about", Vertical).display = True
#
#     def show_tab(self, name: str):
#         """Показывает указанную вкладку"""
#         mapping = {
#             "logs": "tab-logs",
#             "stats": "tab-stats",
#             "settings": "tab-settings",
#             "about": "tab-about",
#         }
#         if name in mapping:
#             self.query_one(Tabs).active = mapping[name]
#
#     async def demo_worker(self):
#         """Демонстрационный воркер"""
#         for i in range(101):
#             self.logs.write(f"📈 Прогресс: {i}%")
#             await asyncio.sleep(0.1)
#
#         # Переключаемся на вкладку статистики
#         self.show_tab("stats")
#         stats = self.query_one("#stats-panel", Static)
#         stats.update("📊 Собрано прокси:\n\nHTTP: 1500\nHTTPS: 800\nSOCKS5: 1200")
#
#
# if __name__ == "__main__":
#     app = TabbedApp()
#     app.run()
