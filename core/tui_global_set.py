from textual.widgets import DataTable, RichLog

# tui_global_set.py
_log_widget_top = None
_log_widget_left = None
_log_widget_right = None
_table_widget = None
_table_initialized = False  # Флаг для отслеживания инициализации
_containers_tabs_3 = None
_current_tab = "stats"  # stats, logs, orders

from textual.containers import Vertical

_containers = {}  # protocol -> container


def register_container(protocol: str, container: Vertical):
    """Глобальная регистрация контейнера"""
    global _containers
    _containers[protocol] = container


def get_container(protocol: str):
    """Глобальное получение контейнера"""
    global _containers
    if protocol and protocol in _containers:
        return _containers[protocol]
    return None


def set_current_tab(tab: str):
    """Устанавливает текущую вкладку"""
    global _current_tab
    _current_tab = tab


def get_current_tab() -> str:
    """Возвращает текущую вкладку"""
    return _current_tab


def set_container_table(widget):
    global _containers_tabs_3
    _containers_tabs_3 = widget


def write_test(msg):
    if _containers_tabs_3:
        _containers_tabs_3.write(msg)
    else:
        return


def update_stats_avg(msg):
    if _containers_tabs_3:
        _containers_tabs_3.clear()
        _containers_tabs_3.write(msg)
    else:
        return


def set_table_widget(widget):
    global _table_widget
    _table_widget = widget


#
# def update_table(stats_data: dict):
#     """Обновляет таблицу статистики"""
#     global _table_widget, _table_initialized
#     if not _table_widget:
#         return
#
#     # Очищаем строки, но оставляем колонки
#     _table_widget.clear()
#
#     # Добавляем колонки ТОЛЬКО один раз
#     if not _table_initialized:
#         _table_widget.add_column("Протокол", key="protocol")
#         _table_widget.add_column("1 порядок", key="order1")
#         _table_widget.add_column("2 порядок", key="order2")
#         _table_widget.add_column("3 порядок", key="order3")
#         _table_widget.add_column("4 порядок", key="order4")
#         _table_widget.add_column("5 порядок", key="order5")
#         _table_widget.add_column("6 порядок", key="order6")
#         _table_widget.add_column("Всего", key="total")
#         _table_initialized = True
#
#     # Добавляем строки для каждого протокола
#     for protocol, orders in stats_data.items():
#         total = sum(orders.values())
#         _table_widget.add_row(
#             protocol,
#             str(orders.get("1", 0)),
#             str(orders.get("2", 0)),
#             str(orders.get("3", 0)),
#             str(orders.get("4", 0)),
#             str(orders.get("5", 0)),
#             str(orders.get("6", 0)),
#             str(total),
#             key=f"row-{protocol}",
#         )
#
#     # Добавляем итоговую строку
#     total_orders = {k: 0 for k in ["1", "2", "3", "4", "5", "6"]}
#     total_all = 0
#     for orders in stats_data.values():
#         for k in total_orders:
#             total_orders[k] += orders.get(k, 0)
#         total_all += sum(orders.values())
#
#     _table_widget.add_row(
#         "📦 ВСЕГО",
#         str(total_orders["1"]),
#         str(total_orders["2"]),
#         str(total_orders["3"]),
#         str(total_orders["4"]),
#         str(total_orders["5"]),
#         str(total_orders["6"]),
#         str(total_all),
#         key="row-total",
#     )
#
# def update_table(stats_data: dict):
#     """Обновляет таблицу статистики"""
#     global _table_widget, _table_initialized
#     if not _table_widget:
#         return
#
#     # Если виджет новый (после пересоздания) — сбрасываем флаг
#     try:
#         _ = _table_widget.columns  # проверяем, жив ли виджет
#     except Exception:
#         return  # виджет мёртв, выходим
#
#     # Очищаем строки, оставляем колонки
#     # Вместо clear() удаляем только строки
#     for row_key in list(_table_widget.rows):
#         _table_widget.remove_row(row_key)
#
#     # Добавляем колонки ТОЛЬКО один раз
#     if not _table_initialized:
#         _table_widget.add_column("Протокол", key="protocol")
#         _table_widget.add_column("1 порядок", key="order1")
#         _table_widget.add_column("2 порядок", key="order2")
#         _table_widget.add_column("3 порядок", key="order3")
#         _table_widget.add_column("4 порядок", key="order4")
#         _table_widget.add_column("5 порядок", key="order5")
#         _table_widget.add_column("6 порядок", key="order6")
#         _table_widget.add_column("Всего", key="total")
#         _table_initialized = True
#
#     # Добавляем строки для каждого протокола
#     for protocol, orders in stats_data.items():
#         total = sum(orders.values())
#         _table_widget.add_row(
#             protocol,
#             str(orders.get("1", 0)),
#             str(orders.get("2", 0)),
#             str(orders.get("3", 0)),
#             str(orders.get("4", 0)),
#             str(orders.get("5", 0)),
#             str(orders.get("6", 0)),
#             str(total),
#             key=f"row-{protocol}",
#         )
#
#     # Добавляем итоговую строку
#     total_orders = {k: 0 for k in ["1", "2", "3", "4", "5", "6"]}
#     total_all = 0
#     for orders in stats_data.values():
#         for k in total_orders:
#             total_orders[k] += orders.get(k, 0)
#         total_all += sum(orders.values())
#
#     _table_widget.add_row(
#         "📦 ВСЕГО",
#         str(total_orders["1"]),
#         str(total_orders["2"]),
#         str(total_orders["3"]),
#         str(total_orders["4"]),
#         str(total_orders["5"]),
#         str(total_orders["6"]),
#         str(total_all),
#         key="row-total",
#     )
#
def update_table(stats_data: dict):
    """Обновляет таблицу статистики"""
    global _table_widget, _table_initialized
    if not _table_widget:
        return

    # Проверяем, есть ли колонки (а не флаг)
    try:
        columns = _table_widget.columns
        has_columns = len(columns) > 0 if columns else False
    except Exception:
        return  # виджет мёртв

    # Если колонок нет — добавляем (независимо от флага)
    if not has_columns:
        _table_widget.add_column("Протокол", key="protocol")
        _table_widget.add_column("1 порядок", key="order1")
        _table_widget.add_column("2 порядок", key="order2")
        _table_widget.add_column("3 порядок", key="order3")
        _table_widget.add_column("4 порядок", key="order4")
        _table_widget.add_column("5 порядок", key="order5")
        _table_widget.add_column("6 порядок", key="order6")
        _table_widget.add_column("Всего", key="total")
    else:
        # Удаляем старые строки, оставляем колонки
        for row_key in list(_table_widget.rows):
            _table_widget.remove_row(row_key)

    # Добавляем строки для каждого протокола
    for protocol, orders in stats_data.items():
        total = sum(orders.values())
        _table_widget.add_row(
            protocol,
            str(orders.get("1", 0)),
            str(orders.get("2", 0)),
            str(orders.get("3", 0)),
            str(orders.get("4", 0)),
            str(orders.get("5", 0)),
            str(orders.get("6", 0)),
            str(total),
            key=f"row-{protocol}",
        )

    # Добавляем итоговую строку
    total_orders = {k: 0 for k in ["1", "2", "3", "4", "5", "6"]}
    total_all = 0
    for orders in stats_data.values():
        for k in total_orders:
            total_orders[k] += orders.get(k, 0)
        total_all += sum(orders.values())

    _table_widget.add_row(
        "📦 ВСЕГО",
        str(total_orders["1"]),
        str(total_orders["2"]),
        str(total_orders["3"]),
        str(total_orders["4"]),
        str(total_orders["5"]),
        str(total_orders["6"]),
        str(total_all),
        key="row-total",
    )


def reset_table():
    """Сбросить таблицу при пересоздании виджета"""
    global _table_initialized, _table_widget
    _table_initialized = False
    _table_widget = None


## top write msg and update and set widget on global data


def set_widget_top(widget):
    global _log_widget_top
    _log_widget_top = widget


def write_top(msg):
    global _log_widget_top
    if _log_widget_top:
        _log_widget_top.write(msg)
    else:
        print(msg)


### set and update,write on right widget
def set_widget_right(widget):
    global _log_widget_right
    _log_widget_right = widget


def update_widget_right(msg):
    global _log_widget_right
    if _log_widget_right:
        _log_widget_right.clear()
        _log_widget_right.write(msg)
    else:
        return


def write_right(msg):
    global _log_widget_right
    if _log_widget_right:
        _log_widget_right.write(msg)
    else:
        print(msg)


### set adn upddate left widget and write
def set_widget_left(widget):
    global _log_widget_left
    _log_widget_left = widget


def write_left(msg):
    global _log_widget_left
    if _log_widget_left:
        _log_widget_left.write(msg)
