/**
 * =============================================================================
 * Process Name: Windows AI Ecosystem Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский контроллер консолидированной панели ИИ-компонентов.
 *   Управляет суб-вкладками «Агенты», «Навыки» и «MCP Серверы»
 *   с поддержкой URL-маршрутизации панелей (#tab-ai-ecosystem#panel-<id>).
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_ai_ecosystem
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-12 02:30:00
 * =============================================================================
 */

(function () {
  'use strict';

  const TAB_ID = 'tab-ai-ecosystem';

  function isAiEcosystemTabActive() {
    const pane = document.getElementById(TAB_ID);
    return pane ? pane.classList.contains('active') : false;
  }

  function normalizeSubTabId(rawId) {
    if (!rawId) return 'agents';
    const s = String(rawId).toLowerCase().trim().replace(/^#/, '').replace(/^panel-/, '');
    if (s.includes('skill')) return 'skills';
    if (s.includes('mcp')) return 'mcp';
    return 'agents';
  }

  function getPanelFromHash() {
    const hash = (typeof location !== 'undefined' ? location.hash : '') || '';
    if (!hash) return null;
    const cleanHash = hash.replace(/^#/, '');
    const parts = cleanHash.split('#');
    if (parts.length >= 2) {
      const mainPart = parts[0];
      if (mainPart === TAB_ID || mainPart === 'ai-ecosystem') {
        return normalizeSubTabId(parts[1]);
      }
    }
    return null;
  }

  function updateUrlWithPanel(panelId) {
    if (typeof history === 'undefined' || typeof location === 'undefined') return;
    const canonical = normalizeSubTabId(panelId);
    const search = location.search || '';
    const newHash = `#${TAB_ID}#panel-${canonical}`;
    if (location.hash !== newHash) {
      try {
        history.replaceState(null, null, `${location.pathname}${search}${newHash}`);
      } catch (_) {}
    }
  }

  function loadScript(src) {
    return new Promise((resolve) => {
      const cleanSrc = src.split('?')[0];
      const existing = document.querySelector(`script[src^="${cleanSrc}"]`);
      if (existing) {
        resolve();
        return;
      }
      const s = document.createElement('script');
      s.type = 'module';
      s.src = src;
      s.onload = () => resolve();
      s.onerror = (err) => {
        console.warn(`[AiEcosystem] Не удалось загрузить скрипт ${src}:`, err);
        resolve();
      };
      document.body.appendChild(s);
    });
  }

  async function loadSubPane(containerId, htmlUrl, jsUrl, initFnName) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const hasMeaningfulContent = container.children.length > 0 && container.innerHTML.trim().length > 30;
    if (!hasMeaningfulContent) {
      try {
        const res = await fetch(`${htmlUrl}?v=${Date.now()}`);
        if (!res.ok) {
          console.warn(`[AiEcosystem] Ошибка загрузки HTML для ${containerId}: HTTP ${res.status}`);
          return;
        }
        container.innerHTML = await res.text();
      } catch (err) {
        console.warn(`[AiEcosystem] Ошибка загрузки HTML для ${containerId}:`, err);
        return;
      }
    }

    if (jsUrl) {
      try {
        await loadScript(`${jsUrl}?v=${Date.now()}`);
        if (initFnName && typeof window[initFnName] === 'function') {
          try {
            window[initFnName]();
          } catch (err) {
            console.debug(`[AiEcosystem] ${initFnName} error:`, err);
          }
        }
      } catch (err) {
        console.warn(`[AiEcosystem] Ошибка скрипта для ${containerId}:`, err);
      }
    }
  }

  function bindSubTabNavEvents() {
    const nav = document.getElementById('ai-ecosystem-subtabs-nav');
    if (!nav || nav.dataset.bound) return;
    nav.dataset.bound = 'true';

    nav.addEventListener('click', (event) => {
      const btn = event.target.closest('button[data-bs-toggle="pill"]');
      if (!btn) return;
      let target = 'agents';
      if (btn.id === 'subtab-ai-skills-btn') target = 'skills';
      else if (btn.id === 'subtab-ai-mcp-btn') target = 'mcp';
      triggerSubTabInit(target);
      updateUrlWithPanel(target);
    });
  }

  async function loadSubPanes() {
    bindSubTabNavEvents();

    // 1. Агенты (активная вкладка по умолчанию)
    await loadSubPane(
      'ai-agents-embed-container',
      '/html/tab_agents/index.html',
      '/html/tab_agents/main.js',
      'initAgentsTab'
    );

    // 2. Навыки и MCP (фоновая предзагрузка)
    await Promise.allSettled([
      loadSubPane(
        'ai-skills-embed-container',
        '/html/tab_skills/index.html',
        '/html/tab_skills/main.js',
        'initSkillsTab'
      ),
      loadSubPane(
        'ai-mcp-embed-container',
        '/html/tab_mcp/index.html',
        '/html/tab_mcp/main.js',
        'initMcpTab'
      ),
    ]);
  }

  async function triggerSubTabInit(subtabName) {
    const canonical = normalizeSubTabId(subtabName);
    if (canonical === 'agents') {
      await loadSubPane('ai-agents-embed-container', '/html/tab_agents/index.html', '/html/tab_agents/main.js', 'initAgentsTab');
      if (typeof window.initAgentsTab === 'function') window.initAgentsTab();
    } else if (canonical === 'skills') {
      await loadSubPane('ai-skills-embed-container', '/html/tab_skills/index.html', '/html/tab_skills/main.js', 'initSkillsTab');
      if (typeof window.initSkillsTab === 'function') window.initSkillsTab();
    } else if (canonical === 'mcp') {
      await loadSubPane('ai-mcp-embed-container', '/html/tab_mcp/index.html', '/html/tab_mcp/main.js', 'initMcpTab');
      if (typeof window.initMcpTab === 'function') window.initMcpTab();
    }
  }

  window.switchAiEcosystemSubTab = function(subtabName, updateUrl = true) {
    const canonical = normalizeSubTabId(subtabName);
    let btnId = 'subtab-ai-agents-btn';
    if (canonical === 'skills') btnId = 'subtab-ai-skills-btn';
    else if (canonical === 'mcp') btnId = 'subtab-ai-mcp-btn';

    const btn = document.getElementById(btnId);
    if (btn) {
      if (window.bootstrap && window.bootstrap.Tab) {
        new window.bootstrap.Tab(btn).show();
      } else {
        btn.click();
      }
      triggerSubTabInit(canonical);
    }
    if (updateUrl) {
      updateUrlWithPanel(canonical);
    }
  };

  async function initAiEcosystemTab() {
    await loadSubPanes();

    window.addEventListener('hashchange', () => {
      if (!isAiEcosystemTabActive()) return;
      const target = getPanelFromHash();
      if (target) {
        window.switchAiEcosystemSubTab(target, false);
      }
    });

    document.addEventListener('tab:activated', (e) => {
      if (e.detail?.tabId === TAB_ID || e.detail?.tabId === 'ai-ecosystem') {
        const target = getPanelFromHash();
        if (target) {
          window.switchAiEcosystemSubTab(target, false);
        } else {
          updateUrlWithPanel('agents');
        }
      }
    });

    const panelFromHash = getPanelFromHash();
    if (panelFromHash) {
      window.switchAiEcosystemSubTab(panelFromHash, false);
    }
  }

  window.initAiEcosystemTab = initAiEcosystemTab;
  window.getAiEcosystemPanelFromHash = getPanelFromHash;
  window.updateAiEcosystemUrlWithPanel = updateUrlWithPanel;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAiEcosystemTab);
  } else {
    initAiEcosystemTab();
  }
})();
