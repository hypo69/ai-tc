/**
 * @file apps/windows/api/webgui/tab_skills/panel_presets/panel.js
 * @description Панель готовых шаблонов навыков (CLI, REST API, парсер данных, AI-персона, мониторинг, генератор отчетов)
 * @author hypo69
 * @version 1.0.0
 * Updated: 2026-11-12 05:00:00
 */

export const SKILL_PRESETS = [
  {
    id: 'tool-automation',
    title: '🛠️ CLI & Python Tool',
    category: 'tools',
    badge: 'Automation',
    description: 'Исполняемый навык с Python-скриптом автоматизации в папке scripts/. Подходит для утилит, конвертеров и системных задач.',
    name: 'custom-cli-tool',
    descRu: 'Автоматизированная CLI утилита для выполнения задач через скрипты.',
    descEn: 'Automated CLI utility providing executable scripts for system routines.',
    purpose: 'Execute specialized automation commands via internal scripts.',
    triggers: 'Triggered when the user requests executing a custom tool or batch script task.',
    protocol: '1. Validate arguments and environment.\n2. Execute python script in `scripts/main.py`.\n3. Return formatted stdout/stderr status.',
    rules: '- Ensure non-zero exit codes are logged and reported.\n- Maintain English logging.',
    hasScript: true,
    scriptCode: `# -*- coding: utf-8 -*-\n"""CLI tool automation script."""\nimport sys\n\ndef main():\n    print("Executing automated tool task...")\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n`,
    hasRef: false,
  },
  {
    id: 'api-connector',
    title: '🌐 REST API Connector',
    category: 'api',
    badge: 'Integration',
    description: 'Интеграция с внешним REST/JSON API. Шаблон с проверкой авторизации, обработкой таймаутов и структурированием ответов.',
    name: 'rest-api-connector',
    descRu: 'Интеграция с внешним сервисом через REST API.',
    descEn: 'Connector skill for external REST API services and endpoints.',
    purpose: 'Query external HTTP REST API endpoints and process JSON payloads.',
    triggers: 'Triggered when user asks to fetch data from or post payloads to remote APIs.',
    protocol: '1. Parse endpoint parameters and auth tokens.\n2. Send HTTP request with exponential retry.\n3. Parse JSON response and summarize.',
    rules: '- Protect sensitive secrets and auth tokens.\n- Handle rate limits and connection timeouts gracefully.',
    hasScript: true,
    scriptCode: `# -*- coding: utf-8 -*-\n"""REST API client script."""\nimport os, urllib.request, json\n\ndef query_api(url: str):\n    req = urllib.request.Request(url, headers={"User-Agent": "ai-tc/1.0"})\n    with urllib.request.urlopen(req, timeout=10) as resp:\n        return json.loads(resp.read().decode("utf-8"))\n`,
    hasRef: true,
    refContent: `# REST API Protocol Guidelines\n\n- Standard timeout: 10s\n- Required headers: User-Agent, Accept\n`,
  },
  {
    id: 'data-parser',
    title: '📊 Data Analyzer & Parser',
    category: 'data',
    badge: 'Analytics',
    description: 'Обработка и анализ структурированных данных (CSV, JSON, XML, таблицы, логи). Извлечение инсайтов и форматирование результатов.',
    name: 'data-analyzer',
    descRu: 'Анализ структурированных данных, логов и таблиц с выводом статистики.',
    descEn: 'Analyze structured data, logs, CSV/JSON datasets, and generate statistics.',
    purpose: 'Parse input data files, compute aggregated metrics, and present visual summaries.',
    triggers: 'Triggered when datasets, spreadsheets or data files need parsing and reporting.',
    protocol: '1. Identify input format (CSV/JSON/Log).\n2. Parse schema and clean invalid rows.\n3. Compute totals, distributions, and outliers.\n4. Output Markdown summary tables.',
    rules: '- Avoid memory leaks on large files.\n- Strictly English docstrings.',
    hasScript: true,
    scriptCode: `# -*- coding: utf-8 -*-\n"""Data parsing helper."""\nimport csv, json\n\ndef parse_records(filepath: str):\n    # Add parser logic here\n    pass\n`,
    hasRef: false,
  },
  {
    id: 'ai-persona',
    title: '🎭 AI Expert & Persona',
    category: 'persona',
    badge: 'Agent Role',
    description: 'Специализированная роль и экспертные инструкции (Архитектор, Аналитик безопасности, Code Reviewer, Консультант).',
    name: 'domain-expert',
    descRu: 'Экспертная роль и правила поведения для специализированных консультаций.',
    descEn: 'Specialized domain expert persona with strict evaluation guidelines.',
    purpose: 'Act as a senior domain expert offering high-level technical feedback.',
    triggers: 'Triggered whenever specialized architectural or domain advice is requested.',
    protocol: '1. Analyze problem from the perspective of domain best practices.\n2. Provide structured pros/cons analysis.\n3. Recommend action plan with trade-offs.',
    rules: '- Be concise, objective, and reference industry standards.',
    hasScript: false,
    hasRef: true,
    refContent: `# Domain Expertise Standards\n\nKey methodologies, architecture patterns, and decision trees.\n`,
  },
  {
    id: 'monitoring-notifier',
    title: '🔔 Monitor & Notifier',
    category: 'monitoring',
    badge: 'Observability',
    description: 'Периодическая проверка сервисов, мониторинг системных параметров, выявление сбоев и отправка нотификаций.',
    name: 'health-monitor',
    descRu: 'Мониторинг доступности сервисов и формирование алертов при сбоях.',
    descEn: 'Health monitoring and alerting skill for infrastructure and services.',
    purpose: 'Continuously verify target service endpoints and notify on anomalies.',
    triggers: 'Triggered by scheduled cron jobs or on-demand health check requests.',
    protocol: '1. Ping healthcheck endpoints.\n2. Measure latency and status codes.\n3. If failure detected, format diagnostic alert.',
    rules: '- Fail-fast on network unreachability.\n- Include timestamps and severity level.',
    hasScript: true,
    scriptCode: `# -*- coding: utf-8 -*-\n"""Health check monitor."""\nimport time\n\ndef check_service(host: str, port: int):\n    # Health probe\n    return True\n`,
    hasRef: false,
  },
  {
    id: 'doc-generator',
    title: '📄 Report & Doc Generator',
    category: 'docgen',
    badge: 'Documentation',
    description: 'Автоматическая генерация документации, отчетов в Markdown/HTML и сводок по проекту на основе входных данных.',
    name: 'report-generator',
    descRu: 'Генератор красивых отчетов, проектной документации и сводок.',
    descEn: 'Automated documentation and structured report generation skill.',
    purpose: 'Generate comprehensive Markdown reports, change logs, and release notes.',
    triggers: 'Triggered when documentation, release summaries or audit reports are requested.',
    protocol: '1. Collect source items and metadata.\n2. Apply template sections and headings.\n3. Format tables and GitHub alerts.\n4. Save output file.',
    rules: '- Follow documentation style standards.\n- Ensure all links and tables are valid.',
    hasScript: false,
    hasRef: true,
    refContent: `# Document Generation Templates\n\nTemplate blocks, header standards, and formatting guidelines.\n`,
  }
];

/**
 * Отрисовка карточек готовых пресетов в контейнере
 */
export function renderPresets() {
  const container = document.getElementById('presets-cards-container');
  if (!container) return;

  container.innerHTML = SKILL_PRESETS.map(p => `
    <div class="col-12 col-md-6 col-lg-4">
      <div class="card bg-dark border-secondary text-white h-100 shadow-sm">
        <div class="card-header border-secondary d-flex justify-content-between align-items-center bg-black bg-opacity-25 py-2">
          <span class="fw-bold small text-white">${p.title}</span>
          <span class="badge bg-primary-subtle text-primary border border-primary-subtle small">${p.badge}</span>
        </div>
        <div class="card-body py-2">
          <p class="card-text text-muted small mb-2" style="min-height: 48px;">
            ${p.description}
          </p>
          <div class="small font-monospace text-secondary mb-2">
            <code>⚡ ${p.name}</code>
          </div>
        </div>
        <div class="card-footer border-secondary bg-black bg-opacity-25 py-2">
          <button type="button" class="btn btn-outline-primary btn-sm w-100 d-flex align-items-center justify-content-center gap-1" onclick="window.skillsTab?.applyPreset('${p.id}')">
            <i class="bi bi-box-arrow-in-right"></i> Использовать шаблон
          </button>
        </div>
      </div>
    </div>
  `).join('');
}
