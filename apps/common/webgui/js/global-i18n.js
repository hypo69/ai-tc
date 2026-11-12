/**
 * =============================================================================
 * Process Name: Windows Web Interface - Global i18n Framework
 * =============================================================================
 * Description:
 *   Единый клиентский модуль сквозной интернационализации (i18n) интерфейса.
 *   Обеспечивает автоопределение языка (URL query, localStorage, navigator.language),
 *   динамическую трансляцию разметки (data-i18n, data-i18n-placeholder, data-i18n-title)
 *   и автоматическое обновление вновь добавляемых элементов через MutationObserver.
 *
 * File: global-i18n.js
 * Project: ai-assistant
 * Package: apps/common/webgui/js
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-10 18:18:00
 * =============================================================================
 */

(function () {
  'use strict';

  const SUPPORTED_LANGS = ['ru', 'en', 'he', 'uk'];
  const DEFAULT_LANG = 'ru';

  const I18nManager = {
    lang: DEFAULT_LANG,
    locale: 'ru-RU',
    translations: {},
    isLoaded: false,
    observer: null,

    init() {
      this.detectLanguage();
      this.syncRtlDirection();
      this.loadTranslations(this.lang).then(() => {
        this.applyTranslations(document);
        this.startObserver();
        window.dispatchEvent(new CustomEvent('i18n:ready', { detail: { lang: this.lang } }));
        window.dispatchEvent(new CustomEvent('i18n:languageChanged', { detail: { lang: this.lang } }));
      });

      // Перехват смены языка через события
      window.addEventListener('storage', (e) => {
        if (e.key === 'app_language' && e.newValue && e.newValue !== this.lang) {
          this.setLanguage(e.newValue);
        }
      });
    },

    syncRtlDirection() {
      const isRtl = (this.lang === 'he' || this.lang === 'ar');
      document.documentElement.setAttribute('dir', isRtl ? 'rtl' : 'ltr');
      document.documentElement.setAttribute('lang', this.lang);
      const offcanvasEl = document.getElementById('leftSideNavOffcanvas');
      if (offcanvasEl) {
        if (isRtl) {
          offcanvasEl.classList.remove('offcanvas-start');
          offcanvasEl.classList.add('offcanvas-end');
        } else {
          offcanvasEl.classList.remove('offcanvas-end');
          offcanvasEl.classList.add('offcanvas-start');
        }
      }
    },

    detectLanguage() {
      // 1. Приоритет: URL query параметры (?lang=ru, ?locale=ru-RU, ?region=ru)
      try {
        const params = new URLSearchParams(window.location.search);
        const urlLang = params.get('lang') || params.get('locale') || params.get('region');
        if (urlLang) {
          const clean = urlLang.toLowerCase().slice(0, 2);
          if (SUPPORTED_LANGS.includes(clean)) {
            this.lang = clean;
            return;
          }
        }
      } catch (e) {
        console.warn('[i18n] Ошибка чтения URL query:', e);
      }

      // 2. LocalStorage
      try {
        const saved = localStorage.getItem('app_language');
        if (saved && SUPPORTED_LANGS.includes(saved)) {
          this.lang = saved;
          return;
        }
      } catch (e) {}

      // 3. Браузер
      try {
        const navLang = (navigator.language || navigator.userLanguage || '').toLowerCase().slice(0, 2);
        if (SUPPORTED_LANGS.includes(navLang)) {
          this.lang = navLang;
          return;
        }
      } catch (e) {}

      this.lang = DEFAULT_LANG;
    },

    async loadTranslations(lang) {
      if (this.translations[lang]) {
        this.isLoaded = true;
        return;
      }

      const paths = [
        `/html/locales/${lang}.json`,
        `/locales/${lang}.json`,
        `locales/${lang}.json`
      ];

      for (const p of paths) {
        try {
          const res = await fetch(p);
          if (res.ok) {
            this.translations[lang] = await res.json();
            this.isLoaded = true;
            return;
          }
        } catch (e) {}
      }

      // Fallback пустой объект
      this.translations[lang] = this.translations[lang] || {};
      this.isLoaded = true;
    },

    t(key, fallback = null) {
      if (!key || typeof key !== 'string') return fallback || '';
      const dict = this.translations[this.lang] || {};
      const parts = key.split('.');
      let val = dict;
      for (const part of parts) {
        if (val && typeof val === 'object' && part in val) {
          val = val[part];
        } else {
          val = null;
          break;
        }
      }
      if (val !== null && val !== undefined && val !== key) {
        return String(val);
      }
      // Каскадный fallback на язык по умолчанию (ru), если в текущем языке ключ отсутствует
      if (this.lang !== DEFAULT_LANG) {
        const ruDict = this.translations[DEFAULT_LANG] || {};
        let ruVal = ruDict;
        for (const part of parts) {
          if (ruVal && typeof ruVal === 'object' && part in ruVal) {
            ruVal = ruVal[part];
          } else {
            ruVal = null;
            break;
          }
        }
        if (ruVal !== null && ruVal !== undefined && ruVal !== key) {
          return String(ruVal);
        }
      }
      return fallback !== null ? fallback : key;
    },

    async setLanguage(newLang) {
      if (!SUPPORTED_LANGS.includes(newLang)) return;
      this.lang = newLang;
      try {
        localStorage.setItem('app_language', newLang);
      } catch (e) {}

      this.syncRtlDirection();
      await this.loadTranslations(newLang);
      this.applyTranslations(document);

      // Оповещаем другие модули (тултипы, селекторы)
      window.dispatchEvent(new CustomEvent('i18n:languageChanged', { detail: { lang: newLang } }));
    },

    applyTranslations(container = document) {
      if (!container || !container.querySelectorAll) return;

      // Текстовое содержимое (data-i18n)
      container.querySelectorAll('[data-i18n]').forEach((el) => {
        const key = el.getAttribute('data-i18n');
        if (key) {
          const translated = this.t(key);
          if (translated && translated !== key) {
            el.innerHTML = translated;
          }
        }
      });

      // Плейсхолдеры (data-i18n-placeholder)
      container.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
        const key = el.getAttribute('data-i18n-placeholder');
        if (key) {
          const translated = this.t(key);
          if (translated && translated !== key) {
            el.setAttribute('placeholder', translated);
          }
        }
      });

      // Заголовки всплывающих подсказок (data-i18n-title)
      container.querySelectorAll('[data-i18n-title]').forEach((el) => {
        const key = el.getAttribute('data-i18n-title');
        if (key) {
          const translated = this.t(key);
          if (translated && translated !== key) {
            el.setAttribute('title', translated);
            el.setAttribute('data-bs-title', translated);
            el.setAttribute('data-original-title', translated);
          }
        }
      });

      // Метки optgroup и элементов с label (data-i18n-label)
      container.querySelectorAll('[data-i18n-label]').forEach((el) => {
        const key = el.getAttribute('data-i18n-label');
        if (key) {
          const translated = this.t(key);
          if (translated && translated !== key) {
            el.setAttribute('label', translated);
            el.label = translated;
          }
        }
      });

      // Атрибуты доступности (data-i18n-aria-label)
      container.querySelectorAll('[data-i18n-aria-label]').forEach((el) => {
        const key = el.getAttribute('data-i18n-aria-label');
        if (key) {
          const translated = this.t(key);
          if (translated && translated !== key) {
            el.setAttribute('aria-label', translated);
          }
        }
      });

      // Заголовок документа (title с data-i18n)
      const pageTitleEl = document.querySelector('title[data-i18n]');
      if (pageTitleEl) {
        const titleKey = pageTitleEl.getAttribute('data-i18n');
        const translatedTitle = this.t(titleKey);
        if (translatedTitle && translatedTitle !== titleKey) {
          document.title = translatedTitle;
        }
      }
    },

    startObserver() {
      if (this.observer) return;
      this.observer = new MutationObserver((mutations) => {
        for (const m of mutations) {
          for (const node of m.addedNodes) {
            if (node.nodeType === Node.ELEMENT_NODE) {
              this.applyTranslations(node);
            }
          }
        }
      });

      this.observer.observe(document.body, { childList: true, subtree: true });
    }
  };

  // Экспорт в глобальную область видимости
  window.i18n = I18nManager;
  document.addEventListener('DOMContentLoaded', () => {
    I18nManager.init();
  });
})();
