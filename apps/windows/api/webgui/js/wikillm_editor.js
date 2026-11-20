/**
 * =============================================================================
 * Process Name: Windows Web Interface - WikiLLM Knowledge Editor
 * =============================================================================
 * Description:
 *   Клиентский компонент интерактивного редактора базы знаний WikiLLM,
 *   статей Markdown и профилей точности RAG.
 *
 * File: wikillm_editor.js
 * Project: ai-tc
 * Package: windows/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 05:00:00
 * =============================================================================
 */

class WikiLLMEditorComponent {
    constructor(containerId = 'wikillm_editor-container') {
        this.container = document.getElementById(containerId);
        this.currentEntity = null;
        this.entities = [];
        this.profiles = [];
        this.activeTab = 'entities'; // 'entities' or 'profiles'
    }

    async init() {
        if (!this.container) return;
        this.renderLayout();
        await this.loadEntities();
        await this.loadProfiles();
    }

    renderLayout() {
        this.container.innerHTML = `
            <div class="card shadow-sm border-secondary-subtle mb-4">
                <div class="card-header d-flex justify-content-between align-items-center py-2" style="background: var(--surface-2); border-bottom: 1px solid var(--border-color); color: var(--text-color);">
                    <h6 class="m-0 fw-bold"><i class="bi bi-journal-bookmark text-primary me-2"></i>Редактор Базы Знаний WikiLLM</h6>
                    <div class="btn-group btn-group-sm" role="group">
                        <button type="button" class="btn btn-sm btn-primary active" id="wikillm-tab-entities-btn" onclick="wikiEditor.switchTab('entities')">
                            <i class="bi bi-file-text me-1"></i>Записи КБ
                        </button>
                        <button type="button" class="btn btn-sm btn-outline-secondary" id="wikillm-tab-profiles-btn" onclick="wikiEditor.switchTab('profiles')">
                            <i class="bi bi-sliders me-1"></i>Профили Точности
                        </button>
                    </div>
                </div>
                <div class="card-body p-3">
                    <div id="wikillm-entities-view">
                        <div class="row g-3">
                            <!-- Left Column: Search & Entity List -->
                            <div class="col-md-4 border-end" style="border-color: var(--border-color) !important;">
                                <div class="input-group mb-2">
                                    <input type="text" id="wikillm-search-input" class="form-control form-control-sm" placeholder="Поиск по КБ..." onkeyup="wikiEditor.filterEntities()">
                                    <button class="btn btn-primary btn-sm" onclick="wikiEditor.createNewEntity()">
                                        <i class="bi bi-plus-lg me-1"></i>Создать
                                    </button>
                                </div>
                                <div id="wikillm-entity-list" class="list-group list-group-flush overflow-auto" style="max-height: 550px;">
                                    <div class="text-center text-muted py-4"><span class="spinner-border spinner-border-sm me-2"></span>Загрузка КБ...</div>
                                </div>
                            </div>

                            <!-- Right Column: Editor Form -->
                            <div class="col-md-8">
                                <form id="wikillm-entity-form" onsubmit="event.preventDefault(); wikiEditor.saveCurrentEntity();">
                                    <div class="d-flex justify-content-between align-items-center mb-3">
                                        <h6 class="fw-bold mb-0" id="wikillm-form-title">Редактирование статьи</h6>
                                        <div>
                                            <button type="button" class="btn btn-outline-danger btn-sm me-2" id="wikillm-delete-btn" onclick="wikiEditor.deleteCurrentEntity()" style="display:none;">
                                                <i class="bi bi-trash me-1"></i>Удалить
                                            </button>
                                            <button type="submit" class="btn btn-primary btn-sm fw-bold">
                                                <i class="bi bi-check-circle me-1"></i>Сохранить статью
                                            </button>
                                        </div>
                                    </div>

                                    <div class="row g-2 mb-2">
                                        <div class="col-md-6">
                                            <label class="form-label form-label-sm fw-semibold mb-1">Ключевой идентификатор (canonical_key)</label>
                                            <input type="text" id="wikillm-key" class="form-control form-control-sm font-monospace" placeholder="win_event_4624" required>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label form-label-sm fw-semibold mb-1">Категория</label>
                                            <input type="text" id="wikillm-category" class="form-control form-control-sm" placeholder="security_audit" required>
                                        </div>
                                    </div>

                                    <div class="mb-2">
                                        <label class="form-label form-label-sm fw-semibold mb-1">Заголовок статьи</label>
                                        <input type="text" id="wikillm-title" class="form-control form-control-sm" placeholder="Успешный вход в систему (Event 4624)" required>
                                    </div>

                                    <div class="mb-2">
                                        <label class="form-label form-label-sm fw-semibold mb-1">Описание / Подробное руководство (Markdown)</label>
                                        <textarea id="wikillm-description" class="form-control form-control-sm font-monospace" rows="6" placeholder="Описание события, риски и контекст..."></textarea>
                                    </div>

                                    <div class="row g-2 mb-2">
                                        <div class="col-md-6">
                                            <label class="form-label form-label-sm fw-semibold mb-1">Утверждения (Claims JSON array)</label>
                                            <textarea id="wikillm-claims" class="form-control form-control-sm font-monospace" rows="3" placeholder='["Вход успешный", "Фиксирует SID"]'></textarea>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label form-label-sm fw-semibold mb-1">Рекомендации (Remediation JSON array)</label>
                                            <textarea id="wikillm-remediation" class="form-control form-control-sm font-monospace" rows="3" placeholder='["Проверить IP", "Сверить Logon Type"]'></textarea>
                                        </div>
                                    </div>

                                    <div class="form-check form-switch mt-2">
                                        <input class="form-check-input" type="checkbox" id="wikillm-verified" checked>
                                        <label class="form-check-label small fw-semibold" for="wikillm-verified">Подтвержденный источник знания (is_verified)</label>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>

                    <!-- Profiles View -->
                    <div id="wikillm-profiles-view" style="display:none;">
                        <h6 class="fw-bold mb-3">Настройки параметров точности и RAG-профилей</h6>
                        <div id="wikillm-profiles-container" class="row g-3">
                            <div class="text-center text-muted py-4"><span class="spinner-border spinner-border-sm me-2"></span>Загрузка профилей...</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    async loadEntities() {
        try {
            const res = await fetch('/api/v1/wikillm/entities');
            if (!res.ok) throw new Error('Failed to fetch entities');
            this.entities = await res.json();
            this.renderEntityList();
        } catch (e) {
            document.getElementById('wikillm-entity-list').innerHTML = `<div class="alert alert-warning p-2 small">Ошибка загрузки КБ: ${e.message}</div>`;
        }
    }

    renderEntityList(filter = '') {
        const listEl = document.getElementById('wikillm-entity-list');
        const search = filter.toLowerCase().trim();
        const filtered = this.entities.filter(e => 
            e.canonical_key.toLowerCase().includes(search) || 
            e.title.toLowerCase().includes(search) ||
            e.category.toLowerCase().includes(search)
        );

        if (filtered.length === 0) {
            listEl.innerHTML = '<div class="text-center text-muted py-3 small">Записи не найдены</div>';
            return;
        }

        listEl.innerHTML = filtered.map(item => `
            <a href="javascript:void(0)" class="list-group-item list-group-item-action py-2 px-2 border-bottom" id="wikillm-item-${item.canonical_key}" onclick="wikiEditor.selectEntity('${item.canonical_key}')">
                <div class="d-flex w-100 justify-content-between align-items-center">
                    <strong class="mb-1 text-truncate small" style="max-width: 180px;">${this.escapeHtml(item.title)}</strong>
                    <span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle font-monospace" style="font-size: 0.7rem;">${this.escapeHtml(item.category)}</span>
                </div>
                <div class="small text-muted font-monospace text-truncate" style="font-size: 0.75rem;">${this.escapeHtml(item.canonical_key)}</div>
            </a>
        `).join('');
    }

    filterEntities() {
        const query = document.getElementById('wikillm-search-input').value;
        this.renderEntityList(query);
    }

    selectEntity(key) {
        const entity = this.entities.find(e => e.canonical_key === key);
        if (!entity) return;

        // Подсветка выбранного элемента в списке
        document.querySelectorAll('#wikillm-entity-list .list-group-item').forEach(el => el.classList.remove('active'));
        const activeItem = document.getElementById(`wikillm-item-${key}`);
        if (activeItem) {
            activeItem.classList.add('active');
        }

        this.currentEntity = entity;
        document.getElementById('wikillm-key').value = entity.canonical_key;
        document.getElementById('wikillm-key').readOnly = true;
        document.getElementById('wikillm-title').value = entity.title;
        document.getElementById('wikillm-category').value = entity.category;
        document.getElementById('wikillm-description').value = entity.description;
        document.getElementById('wikillm-claims').value = JSON.stringify(entity.claims || []);
        document.getElementById('wikillm-remediation').value = JSON.stringify(entity.remediation || []);
        document.getElementById('wikillm-verified').checked = entity.is_verified;
        document.getElementById('wikillm-delete-btn').style.display = 'inline-block';
        document.getElementById('wikillm-form-title').innerText = `Редактирование: ${entity.canonical_key}`;
    }

    createNewEntity() {
        this.currentEntity = null;
        document.querySelectorAll('#wikillm-entity-list .list-group-item').forEach(el => el.classList.remove('active'));
        document.getElementById('wikillm-entity-form').reset();
        document.getElementById('wikillm-key').readOnly = false;
        document.getElementById('wikillm-delete-btn').style.display = 'none';
        document.getElementById('wikillm-form-title').innerText = 'Создание новой статьи КБ';
        document.getElementById('wikillm-key').focus();
    }

    async saveCurrentEntity() {
        let claims = [];
        let remediation = [];

        try {
            const claimsRaw = document.getElementById('wikillm-claims').value.trim();
            claims = claimsRaw ? JSON.parse(claimsRaw) : [];
        } catch(e) {
            alert('Ошибка разбора Claims JSON! Убедитесь в корректности формата массива.');
            return;
        }

        try {
            const remRaw = document.getElementById('wikillm-remediation').value.trim();
            remediation = remRaw ? JSON.parse(remRaw) : [];
        } catch(e) {
            alert('Ошибка разбора Remediation JSON! Убедитесь в корректности формата массива.');
            return;
        }

        const payload = {
            canonical_key: document.getElementById('wikillm-key').value.trim(),
            title: document.getElementById('wikillm-title').value.trim(),
            category: document.getElementById('wikillm-category').value.trim(),
            description: document.getElementById('wikillm-description').value,
            claims: claims,
            remediation: remediation,
            is_verified: document.getElementById('wikillm-verified').checked
        };

        try {
            const res = await fetch('/api/v1/wikillm/entities', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!res.ok) throw new Error('Save failed');
            await this.loadEntities();
            this.selectEntity(payload.canonical_key);
            alert('Статья WikiLLM успешно сохранена!');
        } catch (e) {
            alert(`Ошибка сохранения: ${e.message}`);
        }
    }

    async deleteCurrentEntity() {
        if (!this.currentEntity) return;
        if (!confirm(`Удалить статью '${this.currentEntity.canonical_key}'?`)) return;

        try {
            const res = await fetch(`/api/v1/wikillm/entities/${this.currentEntity.canonical_key}`, {
                method: 'DELETE'
            });
            if (!res.ok) throw new Error('Delete failed');
            await this.loadEntities();
            this.createNewEntity();
            alert('Статья успешно удалена!');
        } catch (e) {
            alert(`Ошибка удаления: ${e.message}`);
        }
    }

    async loadProfiles() {
        try {
            const res = await fetch('/api/v1/wikillm/profiles');
            if (!res.ok) throw new Error('Failed to fetch profiles');
            this.profiles = await res.json();
            this.renderProfiles();
        } catch(e) {
            document.getElementById('wikillm-profiles-container').innerHTML = `<div class="alert alert-warning">Ошибка профилей: ${e.message}</div>`;
        }
    }

    renderProfiles() {
        const container = document.getElementById('wikillm-profiles-container');
        if (!this.profiles || this.profiles.length === 0) {
            container.innerHTML = '<div class="text-muted">Профили не настроены</div>';
            return;
        }

        container.innerHTML = this.profiles.map(p => `
            <div class="col-md-4">
                <div class="card h-100 border-secondary-subtle shadow-sm">
                    <div class="card-header fw-bold d-flex justify-content-between align-items-center py-2" style="background: var(--surface-2); border-bottom: 1px solid var(--border-color); color: var(--text-color);">
                        <span class="text-uppercase">${this.escapeHtml(p.profile_name)}</span>
                        <span class="badge bg-primary-subtle text-primary border border-primary-subtle">${p.score_threshold} score</span>
                    </div>
                    <div class="card-body p-3 small">
                        <div class="mb-2"><strong>Top K / Fetch K:</strong> ${p.top_k} / ${p.fetch_k}</div>
                        <div class="mb-2"><strong>Reranker:</strong> ${p.reranker_enabled ? 'Включен (Top ' + p.rerank_top_n + ')' : 'Отключен'}</div>
                        <div class="mb-2"><strong>Max Tokens:</strong> ${p.max_context_tokens}</div>
                        <div class="mb-2"><strong>Temperature:</strong> ${p.temperature}</div>
                        <div class="mb-2"><strong>Grounding:</strong> ${p.grounding_required ? 'Обязательно' : 'Опционально'}</div>
                    </div>
                </div>
            </div>
        `).join('');
    }

    switchTab(tab) {
        this.activeTab = tab;
        document.getElementById('wikillm-entities-view').style.display = tab === 'entities' ? 'block' : 'none';
        document.getElementById('wikillm-profiles-view').style.display = tab === 'profiles' ? 'block' : 'none';
        
        const entitiesBtn = document.getElementById('wikillm-tab-entities-btn');
        const profilesBtn = document.getElementById('wikillm-tab-profiles-btn');

        if (entitiesBtn) {
            entitiesBtn.classList.toggle('active', tab === 'entities');
            entitiesBtn.classList.toggle('btn-primary', tab === 'entities');
            entitiesBtn.classList.toggle('btn-outline-secondary', tab !== 'entities');
        }

        if (profilesBtn) {
            profilesBtn.classList.toggle('active', tab === 'profiles');
            profilesBtn.classList.toggle('btn-primary', tab === 'profiles');
            profilesBtn.classList.toggle('btn-outline-secondary', tab !== 'profiles');
        }
    }

    escapeHtml(str) {
        return (str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }
}

// Global component initialization and window export
if (typeof window !== 'undefined') {
    window.WikiLLMEditorComponent = WikiLLMEditorComponent;
    if (!window.wikiEditor) {
        window.wikiEditor = new WikiLLMEditorComponent('wikillm_editor-container');
    }
}
