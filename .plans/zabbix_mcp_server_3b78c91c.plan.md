---
name: Zabbix MCP Server
overview: "Пройти полный цикл разработки MCP-сервера для Zabbix: от бизнес-анализа через системный анализ и QA до Python-кода в стиле TDD, используя специализированных субагентов на каждом шаге."
todos:
  - id: step-1-ba
    content: Запустить business-analyst → создать business-analysis.md
    status: pending
  - id: step-2-sa
    content: Запустить python-system-analyst с business-analysis.md → создать system-analysis.md
    status: pending
  - id: step-3-qa
    content: Запустить qa-engineer с system-analysis.md → создать test-cases.md
    status: pending
  - id: step-4-dev
    content: Запустить senior-python-developer (TDD) → реализовать MCP-сервер
    status: pending
isProject: false
---

# Разработка Zabbix MCP-сервера

## Workflow (5 шагов)

```mermaid
flowchart TD
    A[Бизнес-потребность] --> B[business-analyst]
    B --> C["business-analysis.md"]
    C --> D[python-system-analyst]
    D --> E["system-analysis.md"]
    E --> F[qa-engineer]
    F --> G["test-cases.md"]
    G --> H[senior-python-developer]
    H --> I["Готовый MCP-сервер (TDD)"]
```

## Шаги

**Шаг 1: Бизнес-анализ** — `business-analyst`
- Запускаем субагент `business-analyst`
- Результат: `business-analysis.md` — персоны, болевые точки, user stories, функциональные требования к MCP-серверу (10-15 требований, 6-10 user stories)

**Шаг 2: Системный анализ** — `python-system-analyst`
- Входные данные: `business-analysis.md`
- Результат: `system-analysis.md` — архитектура MCP-сервера, технологический стек, API-дизайн, функциональные и нефункциональные требования

**Шаг 3: Тест-кейсы** — `qa-engineer`
- Входные данные: `system-analysis.md`
- Результат: `test-cases.md` — позитивные, негативные, граничные и интеграционные тест-кейсы

**Шаг 4: Разработка кода** — `senior-python-developer` (TDD)
- Входные данные: `system-analysis.md` + `test-cases.md`
- Метод: тест → код → рефакторинг
- Результат: готовый Python-код MCP-сервера с проходящими тестами

## Файловая структура (ожидаемая)

- `business-analysis.md` — выход шага 1
- `system-analysis.md` — выход шага 2
- `test-cases.md` — выход шага 3
- `src/` и `tests/` — выход шага 4
