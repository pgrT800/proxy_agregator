import asyncio
import time
from collections import deque


class AdaptiveSemaphoreController:
    """Адаптивный контроллер для динамического изменения лимита семафора"""

    def __init__(
        self,
        base_limit=50,  # Базовый лимит
        target_pps=1200,  # Целевая нагрузка (пакетов/сек)
        min_limit=5,  # Минимальный лимит
        max_limit=200,  # Максимальный лимит
        inertia=0.3,  # Инерция (плавность изменения)
        avg_window=10,  # Окно усреднения (секунд)
        measurement_interval=5,  # Интервал измерения (секунд)
    ):
        self.base_limit = base_limit
        self.target_pps = target_pps
        self.min_limit = min_limit
        self.max_limit = max_limit
        self.inertia = inertia
        self.avg_window = avg_window
        self.measurement_interval = measurement_interval

        # Хранилище для измерений
        self.pps_history = deque(maxlen=avg_window)
        self.current_limit = base_limit
        self.current_pps = 0
        self.avg_pps = 0
        self.avw = 0  # Average Weighted Load (средневзвешенная нагрузка)

    def get_packet_count(self):
        """Получает общее количество пакетов из /proc/net/dev"""
        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()

            total = 0
            for line in lines[2:]:
                parts = line.split()
                iface = parts[0].strip(":")
                if iface != "lo":  # Исключаем локальную петлю
                    total += int(parts[2])  # RX пакеты
                    total += int(parts[10])  # TX пакеты
            return total
        except:
            return 0

    def measure_pps(self, duration=1):
        """Измеряет текущий PPS (пакетов в секунду)"""
        start = self.get_packet_count()
        time.sleep(duration)
        end = self.get_packet_count()
        return (end - start) / duration

    def calculate_avw(self, current_pps, avg_pps):
        """
        Рассчитывает AWG (средневзвешенную нагрузку)
        AWG = 1 - (средний PPS / текущий PPS)
        Где:
        - AWG < 0: нагрузка выше среднего (перегрузка)
        - AWG > 0: нагрузка ниже среднего (недогрузка)
        - AWG = 0: нагрузка соответствует средней
        """
        if current_pps == 0:
            return 0

        # Нормализованная нагрузка
        load_ratio = avg_pps / current_pps

        # AWG: отрицательное значение = перегрузка
        avw = 1 - load_ratio

        return round(avw, 3)

    def calculate_adaptive_limit(self):
        """
        Рассчитывает адаптивный лимит семафора на основе текущей нагрузки
        Формула: new_limit = base_limit × (target_pps / current_pps)
        """
        if self.current_pps == 0:
            return self.current_limit

        # Рассчитываем новый лимит
        calculated = self.base_limit * (self.target_pps / self.current_pps)

        # Ограничиваем диапазоном
        calculated = max(self.min_limit, min(self.max_limit, calculated))

        # Применяем инерцию (плавное изменение)
        new_limit = (
            self.current_limit + (calculated - self.current_limit) * self.inertia
        )

        return round(new_limit)

    async def update_metrics(self):
        """Однократное обновление метрик (без цикла)"""
        # 1. Измеряем текущий PPS
        pps = self.measure_pps(1)
        self.current_pps = round(pps)

        # 2. Добавляем в историю
        self.pps_history.append(pps)

        # 3. Рассчитываем средний PPS за окно
        if self.pps_history:
            self.avg_pps = round(sum(self.pps_history) / len(self.pps_history))

        # 4. Рассчитываем AWG (средневзвешенную нагрузку)
        self.avw = self.calculate_avw(self.current_pps, self.avg_pps)

        # 5. Рассчитываем адаптивный лимит
        new_limit = self.calculate_adaptive_limit()

        # 6. Обновляем лимит если изменился
        if new_limit != self.current_limit:
            old_limit = self.current_limit
            self.current_limit = new_limit
            return True  # Лимит изменился

        return False  # Лимит не изменился

    async def monitor_loop(self, callback=None):
        """Основной цикл мониторинга

        Args:
            callback: Функция для вывода статуса (например, write_top)
        """
        while True:
            changed = await self.update_metrics()

            # Логируем изменение лимита
            if changed:
                status_text = self.log_status()
                if callback:
                    callback(status_text)
                else:
                    print(status_text)

            # Выводим состояние
            status_text = self.log_status()
            if callback:
                callback(status_text)
            else:
                print(status_text)

            await asyncio.sleep(self.measurement_interval)

    def log_status(self) -> str:
        """Возвращает текущее состояние в виде строки для TUI"""
        output = []

        output.append(f"\n{'='*60}")
        output.append(f"📡 ТЕКУЩЕЕ СОСТОЯНИЕ СЕТИ")
        output.append(f"{'='*60}")
        output.append(f"📦 Текущий PPS:    {self.current_pps}")
        output.append(
            f"📊 Средний PPS:    {self.avg_pps} (за {len(self.pps_history)} сек)"
        )
        output.append(f"⚖️  AWG (нагрузка): {self.avw}")
        output.append(f"🎯 Целевой PPS:    {self.target_pps}")
        output.append(f"🔧 Лимит семафора: {self.current_limit:.0f}")

        # Цветовая индикация AWG
        if self.avw < -0.3:
            output.append(f"⚠️  СОСТОЯНИЕ: КРИТИЧЕСКАЯ ПЕРЕГРУЗКА! 🔴")
        elif self.avw < -0.1:
            output.append(f"⚠️  СОСТОЯНИЕ: Перегрузка 🟡")
        elif self.avw > 0.1:
            output.append(f"✅ СОСТОЯНИЕ: Недогрузка 🟢")
        else:
            output.append(f"✅ СОСТОЯНИЕ: Норма 🟢")

        # Рекомендация
        if self.current_pps > self.target_pps * 1.2:
            output.append(f"💡 Рекомендация: УМЕНЬШИТЬ нагрузку")
        elif self.current_pps < self.target_pps * 0.8:
            output.append(f"💡 Рекомендация: можно УВЕЛИЧИТЬ нагрузку")

        return "\n".join(output)

    def get_current_limit(self):
        """Возвращает текущий адаптивный лимит"""
        return int(self.current_limit)

    def get_status_dict(self):
        """Возвращает статус в виде словаря"""
        return {
            "current_pps": self.current_pps,
            "avg_pps": self.avg_pps,
            "avw": self.avw,
            "semaphore_limit": int(self.current_limit),
            "target_pps": self.target_pps,
            "is_overload": self.avw < -0.1,
        }


# class AdaptiveSemaphore:
#     def __init__(self, controller):
#         self.controller = controller
#         self._lock = asyncio.Lock()
#         self._current_tasks = 0
#
#     async def __aenter__(self):
#         while True:
#             limit = self.controller.get_current_limit()
#             async with self._lock:
#                 if self._current_tasks < limit:
#                     self._current_tasks += 1
#                     break
#             await asyncio.sleep(0.01)  # ждём освобождения
#         return self
#
#     async def __aexit__(self, *args):
#         async with self._lock:
#             self._current_tasks -= 1


#
# # Пример интеграции с TUI
# class TUIExample:
#     def __init__(self):
#         self.controller = AdaptiveSemaphoreController()
#         self.monitor_task = None
#
#     async def start_monitoring(self, write_callback):
#         """Запускает мониторинг с выводом в TUI"""
#         self.monitor_task = asyncio.create_task(
#             self.controller.monitor_loop(callback=write_callback)
#         )
#
#     def stop_monitoring(self):
#         """Останавливает мониторинг"""
#         if self.monitor_task:
#             self.monitor_task.cancel()
#
#     def get_status(self) -> str:
#         """Возвращает однократный статус"""
#         # Обновляем метрики синхронно
#         self.controller.update_metrics()
#         return self.controller.log_status()
#
#
# if __name__ == "__main__":
#     asyncio.run(main())
