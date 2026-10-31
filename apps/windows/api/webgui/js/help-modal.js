/**
 * =============================================================================
 * Process Name: Windows Web Interface - Universal Help Modal Controller
 * =============================================================================
 * Description:
 *   Универсальный контроллер модального окна интерактивной контекстной справки.
 *   Поддерживает:
 *   1. Отображение в стандартном модальном окне 80vw × 80vh (.modal-help).
 *   2. Иерархическую композицию: динамическая сборка атомарных HTML-блоков
 *      через директиву [data-help-include="<url>"].
 *   3. Контекстную навигацию и фокус: открытие как композитной страницы панели,
 *      так и отдельного атомарного блока (с подсветкой и автоскроллом).
 *   4. Полную интеграцию с мульти-темами (CSS-переменные) и мультиязычностью
 *      (window.i18n.applyTranslations).
 *   5. Автоматическое делегирование кликов по элементам [data-help-url] и [data-help-target].
 *
 * Usage Examples:
 *   HTML Trigger (Composite Panel):
 *     <button class="btn btn-sm btn-outline-secondary"
 *             data-help-url="/html/tab_log_settings/help/index.html"
 *             data-help-title="Справка по журналам">
 *       <i class="bi bi-question-circle"></i>
 *     </button>
 *
 *   HTML Trigger (Direct Block Focus):
 *     <button class="btn btn-xs btn-outline-secondary"
 *             data-help-url="/html/tab_log_settings/help/index.html"
 *             data-help-focus="block_kpi_cards">
 *       <i class="bi bi-question-circle"></i>
 *     </button>
 *
 *   JavaScript API:
 *     window.HelpModal.openUrl('/html/tab_log_settings/help/index.html', { focusBlock: 'block_kpi_cards' });
 *
 * File: help-modal.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 19:16:00
 * =============================================================================
 */

(function (window, document) {
  'use strict';

  // Кеш загруженных фрагментов справки для оптимизации сетевых запросов
  const helpCache = new Map();

  class HelpModalController {
    constructor() {
      this.modalEl = null;
      this.bsModal = null;
      this.currentFocusBlock = null;
      this._init();
    }

    /**
     * Инициализация контроллера и глобального слушателя событий
     * @private
     */
    _init() {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => this._bindGlobalTriggers());
      } else {
        this._bindGlobalTriggers();
      }
    }

    /**
     * Обеспечивает существование DOM-элемента модального окна #help-modal
     * @returns {HTMLElement}
     * @private
     */
    _ensureModalElement() {
      let modalEl = document.getElementById('help-modal');
      if (!modalEl) {
        const modalHtml = `
          <div class="modal fade modal-help" id="help-modal" tabindex="-1" aria-labelledby="help-modal-label" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
              <div class="modal-content shadow border-subtle">
                <div class="modal-header py-2 px-3 bg-body-tertiary border-bottom border-subtle">
                  <div class="d-flex align-items-center gap-2">
                    <i class="bi bi-question-diamond text-primary fs-5"></i>
                    <h5 class="modal-title fs-6 fw-bold mb-0 text-body" id="help-modal-label" data-i18n="helpModal.title">
                      Интерактивная справка
                    </h5>
                  </div>
                  <div class="d-flex align-items-center gap-2">
                    <button type="button" class="btn btn-xs btn-outline-secondary d-none" id="help-btn-all-blocks" title="Показать все блоки">
                      <i class="bi bi-arrows-expand me-1"></i><span data-i18n="helpModal.btnShowAll">Все разделы</span>
                    </button>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                  </div>
                </div>
                <div class="modal-body p-3 overflow-auto" id="help-modal-content" style="max-height: calc(80vh - 110px);">
                  <div class="d-flex align-items-center justify-content-center py-5">
                    <div class="spinner-border text-primary spinner-border-sm me-2" role="status"></div>
                    <span class="small text-muted" data-i18n="common.loading">Загрузка справки...</span>
                  </div>
                </div>
                <div class="modal-footer py-2 px-3 bg-body-tertiary border-top border-subtle d-flex justify-content-between">
                  <span class="small text-muted" id="help-modal-status-text"></span>
                  <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal" data-i18n="helpModal.close">
                    Закрыть
                  </button>
                </div>
              </div>
            </div>
          </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        modalEl = document.getElementById('help-modal');
      }

      this.modalEl = modalEl;
      if (window.bootstrap && !this.bsModal) {
        this.bsModal = new window.bootstrap.Modal(modalEl, { keyboard: true, focus: true });
      }

      // Снятие фокуса с внутренних кнопок перед закрытием для предотвращения ошибки WAI-ARIA aria-hidden
      if (!modalEl._hideAriaBound) {
        modalEl._hideAriaBound = true;
        modalEl.addEventListener('hide.bs.modal', () => {
          if (document.activeElement && modalEl.contains(document.activeElement)) {
            document.activeElement.blur();
          }
        });
      }

      // Привязка обработчика кнопки «Все разделы»
      const showAllBtn = modalEl.querySelector('#help-btn-all-blocks');
      if (showAllBtn && !showAllBtn._bound) {
        showAllBtn._bound = true;
        showAllBtn.addEventListener('click', () => {
          this.resetBlockFocus();
        });
      }

      return modalEl;
    }

    /**
     * Делегированный перехват кликов по кнопкам вызова справки
     * @private
     */
    _bindGlobalTriggers() {
      document.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-help-url], [data-help-target]');
        if (!trigger) return;

        event.preventDefault();
        const url = trigger.getAttribute('data-help-url');
        const focusBlock = trigger.getAttribute('data-help-focus') || trigger.getAttribute('data-help-target');
        const title = trigger.getAttribute('data-help-title');

        if (url) {
          this.openUrl(url, { focusBlock, title });
        } else if (focusBlock) {
          this.highlightBlock(focusBlock);
        }
      });
    }

    /**
     * Загрузка HTML-содержимого по URL с локальным кешированием
     * @param {string} url - URL адрес фрагмента
     * @returns {Promise<string>}
     */
    async fetchFragment(url) {
      if (helpCache.has(url)) {
        return helpCache.get(url);
      }
      try {
        const resp = await fetch(url, { cache: 'no-cache' });
        if (!resp.ok) {
          throw new Error(`Ошибка загрузки справки HTTP ${resp.status}: ${url}`);
        }
        const text = await resp.text();
        helpCache.set(url, text);
        return text;
      } catch (err) {
        console.error('[HelpModal] Ошибка загрузки справки:', err);
        return `
          <div class="alert alert-warning small mb-0">
            <i class="bi bi-exclamation-triangle me-1"></i>
            Не удалось загрузить блок справки: <code>${url}</code>
          </div>
        `;
      }
    }

    /**
     * Рекурсивное разрешение директив [data-help-include]
     * Собирает составные панели из атомарных блоков
     * @param {HTMLElement} container
     * @returns {Promise<void>}
     */
    async resolveIncludes(container) {
      const includePlaceholders = Array.from(container.querySelectorAll('[data-help-include]'));
      if (includePlaceholders.length === 0) return;

      const loadPromises = includePlaceholders.map(async (placeholder) => {
        const includeUrl = placeholder.getAttribute('data-help-include');
        if (!includeUrl) return;

        const html = await this.fetchFragment(includeUrl);
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html.trim();

        // Рекурсивно разрешаем вложенные инклюды если есть
        await this.resolveIncludes(tempDiv);

        placeholder.replaceWith(...tempDiv.childNodes);
      });

      await Promise.all(loadPromises);
    }

    /**
     * Открытие модального окна справки по URL страницы или атомарного блока
     * @param {string} url - URL HTML-файла справки
     * @param {Object} [options]
     * @param {string} [options.focusBlock] - ID блока для подсветки и автоскролла
     * @param {string} [options.title] - Заголовок модального окна
     */
    async openUrl(url, options = {}) {
      const modalEl = this._ensureModalElement();
      const contentEl = modalEl.querySelector('#help-modal-content');
      const titleEl = modalEl.querySelector('#help-modal-label');
      const showAllBtn = modalEl.querySelector('#help-btn-all-blocks');

      if (options.title && titleEl) {
        titleEl.textContent = options.title;
        titleEl.removeAttribute('data-i18n');
      }

      contentEl.innerHTML = `
        <div class="d-flex align-items-center justify-content-center py-5">
          <div class="spinner-border text-primary spinner-border-sm me-2" role="status"></div>
          <span class="small text-muted">Загрузка справки...</span>
        </div>
      `;

      if (this.bsModal) {
        this.bsModal.show();
      }

      try {
        const rootHtml = await this.fetchFragment(url);
        const tempContainer = document.createElement('div');
        tempContainer.innerHTML = rootHtml;

        // Иерархическая композиция: подгружаем все атомарные блоки
        await this.resolveIncludes(tempContainer);

        // Инъекция собранного DOM
        contentEl.innerHTML = '';
        while (tempContainer.firstChild) {
          contentEl.appendChild(tempContainer.firstChild);
        }

        // Применяем мультиязычность
        if (window.i18n && typeof window.i18n.applyTranslations === 'function') {
          window.i18n.applyTranslations(modalEl);
        }

        // Привязка кнопок локального перехода [data-help-jump]
        contentEl.querySelectorAll('[data-help-jump]').forEach((btn) => {
          btn.addEventListener('click', (e) => {
            e.preventDefault();
            const targetBlock = btn.getAttribute('data-help-jump');
            if (targetBlock) {
              this.highlightBlock(targetBlock, true);
            }
          });
        });

        // Если указан целевой блок — активируем фокус
        if (options.focusBlock) {
          setTimeout(() => {
            this.highlightBlock(options.focusBlock, false);
            if (showAllBtn) showAllBtn.classList.remove('d-none');
          }, 100);
        } else {
          if (showAllBtn) showAllBtn.classList.add('d-none');
        }
      } catch (err) {
        console.error('[HelpModal] Ошибка формирования справки:', err);
        contentEl.innerHTML = `
          <div class="alert alert-danger small">
            <h6 class="fw-bold mb-1"><i class="bi bi-x-circle me-1"></i>Ошибка загрузки справки</h6>
            <span>${err.message || err}</span>
          </div>
        `;
      }
    }

    /**
     * Подсветка конкретного атомарного блока и скролл к нему
     * @param {string} blockId
     * @param {boolean} [scrollOnly=false]
     */
    highlightBlock(blockId, scrollOnly = false) {
      if (!this.modalEl) return;
      const targetEl = this.modalEl.querySelector(`[data-help-block="${blockId}"]`);
      if (!targetEl) return;

      const contentEl = this.modalEl.querySelector('#help-modal-content');
      const allBlocks = this.modalEl.querySelectorAll('[data-help-block]');

      if (!scrollOnly) {
        allBlocks.forEach((b) => {
          b.classList.remove('border-primary', 'shadow');
          b.style.opacity = '0.5';
        });
        targetEl.classList.add('border-primary', 'shadow');
        targetEl.style.opacity = '1';
        this.currentFocusBlock = blockId;
      }

      targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    /**
     * Сброс фокуса на все блоки (показать все блоки в полном виде)
     */
    resetBlockFocus() {
      if (!this.modalEl) return;
      const allBlocks = this.modalEl.querySelectorAll('[data-help-block]');
      allBlocks.forEach((b) => {
        b.classList.remove('border-primary', 'shadow');
        b.style.opacity = '1';
      });
      const showAllBtn = this.modalEl.querySelector('#help-btn-all-blocks');
      if (showAllBtn) showAllBtn.classList.add('d-none');
      this.currentFocusBlock = null;
    }
  }

  // Экспорт синглтона в глобальный контекст
  window.HelpModal = new HelpModalController();
  window.openHelpModal = (url, options) => window.HelpModal.openUrl(url, options);

})(window, document);
