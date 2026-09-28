import asyncio

# import tui_global_set
from textual.containers import Horizontal
from textual.widgets import ProgressBar, Static

from core.tui_global_set import get_container, register_container, write_top


class DynamicWorkerWidget(Static):
    """Виджет для динамического отображения задачи"""

    def __init__(self, task_id: str, task_name: str, protocol: str = "http"):
        super().__init__()
        self.task_id = task_id
        self.task_name = task_name
        self.widget_id = task_id
        self.protocol = protocol
        self._ready = False
        self._pending_stage = None
        self._pending_progress = None
        self._pending_status = None
        self._start_time = asyncio.get_event_loop().time()

    def compose(self):
        with Horizontal(classes="dynamic-worker-row"):
            yield Static(f"{self.task_name}", classes="task-name")
            yield Static("", id=f"stage-{self.widget_id}", classes="task-stage")
            yield ProgressBar(
                total=100,
                show_percentage=True,
                id=f"progress-{self.widget_id}",
            )
            yield Static("", id=f"status-{self.widget_id}", classes="task-status")
            yield Static("", id=f"summary-{self.widget_id}", classes="summary-text")

    def on_mount(self):
        self._ready = True
        self.call_after_refresh(self._apply_pending_updates)

    def _apply_pending_updates(self):
        if self._pending_stage:
            self._update_stage_now(self._pending_stage)
            self._pending_stage = None
        if self._pending_progress:
            self._update_progress_now(self._pending_progress)
            self._pending_progress = None
        if self._pending_status:
            self._update_status_now(self._pending_status)
            self._pending_status = None

    def _element_exists(self, element_id: str) -> bool:
        try:
            self.query_one(element_id)
            return True
        except:
            return False

    def _update_stage_now(self, stage: str):
        try:
            element_id = f"#stage-{self.widget_id}"
            if self._element_exists(element_id):
                self.query_one(element_id, Static).update(stage)
        except Exception as e:
            write_top(f"[DEBUG] Update stage error: {e}")

    def update_stage(self, stage: str):
        if not self._ready:
            self._pending_stage = stage
            return
        self._update_stage_now(stage)

    def _update_progress_now(self, value: int):
        try:
            element_id = f"#progress-{self.widget_id}"
            if self._element_exists(element_id):
                self.query_one(element_id, ProgressBar).update(progress=value)
        except Exception as e:
            write_top(f"[DEBUG] Update progress error: {e}")

    def update_total(self, total: int):
        """Обновляет максимальное значение прогресс-бара"""
        if self._ready:
            try:
                element_id = f"#progress-{self.widget_id}"
                if self._element_exists(element_id):
                    self.query_one(element_id, ProgressBar).update(total=total)
            except Exception as e:
                write_top(f"[DEBUG] Update total error: {e}")

    def update_progress(self, value: int):
        if not self._ready:
            self._pending_progress = value
            return
        self._update_progress_now(value)

    def add_progress(self, value: int):
        """Увеличивает прогресс на указанное значение"""
        if self._ready:
            try:
                element_id = f"#progress-{self.widget_id}"
                if self._element_exists(element_id):
                    progress_bar = self.query_one(element_id, ProgressBar)
                    current = progress_bar.progress
                    new_value = current + value
                    progress_bar.update(progress=new_value)
            except Exception as e:
                write_top(f"[DEBUG] Add progress error: {e}")

    def _update_status_now(self, status: str):
        icons = {"waiting": "⏳", "running": "🔄", "done": "✅", "error": "❌"}
        try:
            element_id = f"#status-{self.widget_id}"
            if self._element_exists(element_id):
                self.query_one(element_id, Static).update(icons.get(status, "⏳"))
        except Exception as e:
            write_top(f"[DEBUG] Update status error: {e}")

    def update_status(self, status: str):
        if not self._ready:
            self._pending_status = status
            return
        self._update_status_now(status)

    def complete(self, processed: int):
        """Завершает виджет со статистикой"""
        if self._ready:
            elapsed = asyncio.get_event_loop().time() - self._start_time
            summary = f"✅ {processed} | {elapsed:.0f}с"
            self.query_one(f"#summary-{self.widget_id}", Static).update(summary)
            # self.update_progress(100)
            # self.update_status("done")
            # self.update_stage("✅ Готов")


class TUIManager:
    _instance = None
    _active_widgets = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # Регистрация контейнера через глобальную функцию
    def register_container(self, protocol: str, container):
        register_container(protocol, container)
        # write_top(f"[DEBUG] Container registered for protocol: {protocol}")

    # Получение контейнера через глобальную функцию
    def get_container(self, protocol: str = None):
        return get_container(protocol)

    async def create_task_widget(
        self, task_id: str, task_name: str, protocol: str = "http"
    ):
        if task_id not in self._active_widgets:
            # write_top(f"[DEBUG] Creating widget: {task_id} for protocol {protocol}")

            container = self.get_container(protocol)
            if container is None:
                # write_top(f"[DEBUG] ERROR: Container for protocol {protocol} not set!")
                return None

            widget = DynamicWorkerWidget(task_id, task_name, protocol)
            self._active_widgets[task_id] = widget

            # write_top(f"[DEBUG] Mounting to container for {protocol}")
            await container.mount(widget)
            # write_top(f"[DEBUG] Widget mounted: {task_id}")

            widget.display = True
            container.refresh()
            return widget
        return self._active_widgets[task_id]

    def update_task_stage(self, task_id: str, stage: str):
        if task_id in self._active_widgets:
            self._active_widgets[task_id].update_stage(stage)
        else:
            write_top(f"[DEBUG] Task {task_id} not found in active widgets")

    def update_task_progress(self, task_id: str, value: int):
        if task_id in self._active_widgets:
            self._active_widgets[task_id].update_progress(value)

    def update_task_total(self, task_id: str, total: int):
        """Обновляет максимальное значение прогресс-бара"""
        if task_id in self._active_widgets:
            self._active_widgets[task_id].update_total(total)

    def add_task_progress(self, task_id: str, value: int):
        """Увеличивает прогресс на значение"""
        if task_id in self._active_widgets:
            self._active_widgets[task_id].add_progress(value)

    def update_task_status(self, task_id: str, status: str):
        if task_id in self._active_widgets:
            self._active_widgets[task_id].update_status(status)

    def complete_task(self, task_id: str, processed: int):
        if task_id in self._active_widgets:
            self._active_widgets[task_id].complete(processed)

    def remove_task(self, task_id: str):
        if task_id in self._active_widgets:
            widget = self._active_widgets[task_id]
            container = self.get_container(widget.protocol)
            if container and widget in container.children:
                asyncio.create_task(widget.remove())
            del self._active_widgets[task_id]


tui_manager = TUIManager()


async def register_task(task_id: str, task_name: str, protocol: str = "http"):
    # write_top(f"[DEBUG] register_task: {task_id} for protocol {protocol}")
    return await tui_manager.create_task_widget(task_id, task_name, protocol)


def update_task(
    task_id: str,
    stage: str = None,
    progress: int = None,
    add: int = None,
    total: int = None,
    status: str = None,
    processed: int = None,
):
    if stage is not None:
        tui_manager.update_task_stage(task_id, stage)
    if progress is not None:
        tui_manager.update_task_progress(task_id, progress)
    if add is not None:
        tui_manager.add_task_progress(task_id, add)
    if total is not None:
        tui_manager.update_task_total(task_id, total)
    if status is not None:
        tui_manager.update_task_status(task_id, status)
    if processed is not None:
        tui_manager.complete_task(task_id, processed)
