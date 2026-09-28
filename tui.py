import asyncio

from textual.app import App
from textual.containers import Horizontal
from textual.widgets import RichLog


class MyApp(App):
    CSS = """
    Horizontal {
        height: 100%;
    }
    
    RichLog {
        width: 50%;
        border: solid white;
    }
    """

    def compose(self):
        with Horizontal():
            yield RichLog(id="left")  # левое окно с ID
            yield RichLog(id="right")  # правое окно с ID

    def on_mount(self):
        asyncio.create_task(self.counter())

    async def counter(self):
        # Находим виджеты по ID
        left = self.query_one("#left", RichLog)
        right = self.query_one("#right", RichLog)

        for i in range(100):
            left.write(str(i))  # пишем в левое окно
            right.write(str(i))  # пишем в правое окно
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    app = MyApp()
    app.run()
