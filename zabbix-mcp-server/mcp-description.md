# Zabbix MCP — описание инструментов

Примеры ниже получены вызовом реализации тулов против **Zabbix 7.0** (Docker, `http://localhost:8081`) и типичного хоста **Zabbix server**. Ответы MCP — это **строки** (часто JSON); в Cursor аргументы передаются как JSON-объект.

Скрипт для повторного сбора примеров: `python scripts/collect_mcp_tool_samples.py` (из каталога проекта, с настроенным `.env`).

---

### get_active_problems

Активные проблемы Zabbix: фильтры по имени хоста, группе, уровню серьёзности (0–5), признаку подтверждения. Имена хостов подставляются через `trigger.get` (совместимость с Zabbix 7).

**Пример запроса (аргументы MCP):**

```json
{}
```

**Пример ответа:**

```
[
  {
    "problem_id": "23",
    "host": "Zabbix server",
    "description": "Linux: Zabbix agent is not available (for 3m)",
    "severity": "Average",
    "severity_level": 3,
    "since": "2026-04-17T20:30:26+00:00",
    "acknowledged": true
  }
]
```

---

### acknowledge_problem

Подтверждение проблемы по `problem_id` (event id) с обязательным комментарием; опционально закрыть проблему (`close`).

**Пример запроса (аргументы MCP):**

```json
{
  "problem_id": "23",
  "comment": "MCP mcp-description.md sample ack",
  "close": false
}
```

**Пример ответа:**

```
Problem 23 acknowledged successfully.
```

---

### get_incident_summary

Сводка по инциденту: либо один `problem_id`, либо окно `time_from` / `time_to` (ISO-8601).

**Пример запроса (аргументы MCP):**

```json
{
  "problem_id": null,
  "time_from": "2026-04-11T00:00:00Z",
  "time_to": "2026-04-18T23:59:59Z"
}
```

**Пример ответа:**

```
{
  "total_problems": 1,
  "affected_hosts": [
    "Zabbix server"
  ],
  "problems_by_severity": {
    "Average": 1
  },
  "event_timeline": [
    {
      "problem_id": "23",
      "description": "Linux: Zabbix agent is not available (for 3m)",
      "started": "2026-04-17T20:30:26+00:00",
      "resolved": "still active"
    }
  ],
  "period": {
    "from": "2026-04-11T00:00:00+00:00",
    "to": "2026-04-18T23:59:59+00:00"
  }
}
```

---

### create_maintenance

Создание окна обслуживания по имени (идемпотентно по `name`). Нужен `host` и/или `host_group`.

**Пример запроса (аргументы MCP):**

```json
{
  "name": "mcp-doc-maint-1776508235",
  "reason": "MCP documentation sample",
  "duration_minutes": 30,
  "host": "Zabbix server",
  "host_group": null
}
```

**Пример ответа:**

```
{
  "maintenance_id": "3",
  "status": "created"
}
```

---

### add_host

Добавить хост с интерфейсом агента и группами; идемпотентно по техническому имени.

**Пример запроса (аргументы MCP):**

```json
{
  "name": "mcp_doc_host_1776508235",
  "ip": "127.0.0.1",
  "host_groups": ["Zabbix servers"],
  "templates": null,
  "dns": "",
  "port": "10050"
}
```

**Пример ответа:**

```
{
  "host_id": "10684",
  "status": "created"
}
```

---

### search_hosts

Поиск хостов по подстроке имени, группе, шаблону или тегу. Пустой запрос возвращает первую страницу хостов (ограничение `ZABBIX_PAGE_LIMIT`).

**Пример запроса (аргументы MCP):**

```json
{}
```

**Пример ответа (фрагмент):**

```
[
  {
    "host_id": "10084",
    "name": "Zabbix server",
    "technical_name": "Zabbix server",
    "status": "Monitored",
    "availability": "Unknown",
    "ip": "127.0.0.1",
    "groups": ["Zabbix servers"]
  }
]
```

---

### check_host_availability

Доступность Zabbix agent по основному интерфейсу хоста.

**Пример запроса (аргументы MCP):**

```json
{
  "host": "Zabbix server"
}
```

**Пример ответа:**

```
{
  "host": "Zabbix server",
  "available": false,
  "status": "Unavailable",
  "ip": "127.0.0.1",
  "last_error": "Get value from agent failed: Cannot establish TCP connection to [[127.0.0.1]:10050]: [111] Connection refused"
}
```

---

### get_metric_value

Последнее значение метрики по ключу и хосту (`host` или `host_id`).

**Пример запроса (аргументы MCP):**

```json
{
  "item_key": "agent.ping",
  "host": "Zabbix server"
}
```

**Пример ответа:**

```
{
  "item_key": "agent.ping",
  "host": "Zabbix server",
  "value": "0",
  "units": "",
  "last_updated": null
}
```

---

### get_metric_history

История метрики за интервал (ISO-8601 UTC).

**Пример запроса (аргументы MCP):**

```json
{
  "item_key": "agent.ping",
  "time_from": "2026-04-18T08:30:35Z",
  "time_to": "2026-04-18T10:30:35Z",
  "host": "Zabbix server"
}
```

**Пример ответа:**

```
[]
```

---

### export_metrics

Экспорт истории по списку хостов и ключей; `format`: `json` или `csv`.

**Пример запроса (аргументы MCP):**

```json
{
  "hosts_list": ["Zabbix server"],
  "items_list": ["agent.ping"],
  "time_from": "2026-04-18T08:30:35Z",
  "time_to": "2026-04-18T10:30:35Z",
  "format": "json"
}
```

**Пример ответа:**

```
[]
```

---

### get_triggers

Список триггеров на хосте (краткие поля: выражение, состояние, приоритет).

**Пример запроса (аргументы MCP):**

```json
{
  "host": "Zabbix server"
}
```

**Пример ответа (первые элементы; всего десятки записей):**

```
[
  {
    "trigger_id": "13075",
    "description": "Zabbix server: Excessive value cache usage",
    "expression": "{33803}>{$ZABBIX.SERVER.UTIL.MAX:\"value cache\"}",
    "state": 0,
    "status": "Enabled",
    "priority": 3,
    "last_change": 0
  },
  {
    "trigger_id": "13436",
    "description": "Zabbix server: Utilization of vmware collector processes is high",
    "expression": "{33801}>{$ZABBIX.SERVER.UTIL.MAX:\"vmware collector\"}",
    "state": 1,
    "status": "Enabled",
    "priority": 3,
    "last_change": 0
  }
]
```

---

### create_trigger

Создание триггера после локальной проверки синтаксиса выражения (должна быть функция вида `last(/Имя хоста/item.key)>0`; в имени хоста допускаются пробелы).

**Пример запроса (аргументы MCP):**

```json
{
  "name": "MCP doc trigger 1776508235",
  "expression": "last(/Zabbix server/agent.ping)>0",
  "priority": 1,
  "description": "Sample from MCP docs collector"
}
```

**Пример ответа:**

```
{
  "trigger_id": "25224",
  "status": "created"
}
```

---

### search_items

Поиск элементов данных по подстроке имени, ключа или описания; опционально `host_id`.

**Пример запроса (аргументы MCP):**

```json
{
  "key_substring": "agent.ping"
}
```

**Пример ответа (фрагмент; в выдаче много шаблонных хостов):**

```
[
  {
    "item_id": "42237",
    "name": "Zabbix agent ping",
    "key_": "agent.ping",
    "host": "Zabbix server",
    "units": "",
    "description": "The agent always returns \"1\" for this item. May be used in combination with `nodata()` for the availability check.",
    "last_value": "0"
  }
]
```

---

### bulk_update_macro

Массовое создание/обновление пользовательского макроса на хостах по шаблону имени или тегу.

**Пример запроса (аргументы MCP):**

```json
{
  "macro": "{$MCP_DOC_MACRO}",
  "value": "1",
  "name_pattern": "mcp_doc_host_1776508235",
  "tag": null
}
```

**Пример ответа:**

```
{
  "updated_count": 1,
  "total_matched_hosts": 1,
  "macro": "{$MCP_DOC_MACRO}",
  "new_value": "1"
}
```

---

### get_availability_report

Оценка аптайма по истории проблем за календарный период (даты `YYYY-MM-DD` или полный ISO).

**Пример запроса (аргументы MCP):**

```json
{
  "hosts_list": ["Zabbix server"],
  "time_from": "2026-04-11",
  "time_to": "2026-04-18"
}
```

**Пример ответа:**

```
[
  {
    "host": "Zabbix server",
    "uptime_percent": 99.7067,
    "downtime_seconds": 1774,
    "uptime_seconds": 603026,
    "period_seconds": 604800,
    "period": {
      "from": "2026-04-10T21:00:00+00:00",
      "to": "2026-04-17T21:00:00+00:00"
    }
  }
]
```