/**
 * =============================================================================
 * Process Name: Windows AI Ecosystem Tab - Main Script
 * =============================================================================
 * Description:
 *   Клиентский контроллер консолидированной панели ИИ-компонентов.
 *   Управляет суб-вкладками «Агенты», «Навыки» и «MCP Серверы».
 *
 * File: main.js
 * Project: ai-windows-admin
 * Package: windows/api/webgui/tab_ai_ecosystem
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-30 11:15:00
 * =============================================================================
 */

(function () {
  'use strict';

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

    // Проверяем наличие значимого содержимого в контейнере
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
      if (btn.id === 'subtab-ai-agents-btn') triggerSubTabInit('agents');
      else if (btn.id === 'subtab-ai-skills-btn') triggerSubTabInit('skills');
      else if (btn.id === 'subtab-ai-mcp-btn') triggerSubTabInit('mcp');
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
    if (subtabName === 'agents') {
      await loadSubPane('ai-agents-embed-container', '/html/tab_agents/index.html', '/html/tab_agents/main.js', 'initAgentsTab');
      if (typeof window.initAgentsTab === 'function') window.initAgentsTab();
    } else if (subtabName === 'skills') {
      await loadSubPane('ai-skills-embed-container', '/html/tab_skills/index.html', '/html/tab_skills/main.js', 'initSkillsTab');
      if (typeof window.initSkillsTab === 'function') window.initSkillsTab();
    } else if (subtabName === 'mcp') {
      await loadSubPane('ai-mcp-embed-container', '/html/tab_mcp/index.html', '/html/tab_mcp/main.js', 'initMcpTab');
      if (typeof window.initMcpTab === 'function') window.initMcpTab();
    }
  }

  window.switchAiEcosystemSubTab = function(subtabName) {
    let btnId = 'subtab-ai-agents-btn';
    if (subtabName === 'skills') btnId = 'subtab-ai-skills-btn';
    else if (subtabName === 'mcp') btnId = 'subtab-ai-mcp-btn';

    const btn = document.getElementById(btnId);
    if (btn) {
      if (window.bootstrap && window.bootstrap.Tab) {
        new window.bootstrap.Tab(btn).show();
      } else {
        btn.click();
      }
      triggerSubTabInit(subtabName);
    }
  };

  async function initAiEcosystemTab() {
    await loadSubPanes();
  }

  window.initAiEcosystemTab = initAiEcosystemTab;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAiEcosystemTab);
  } else {
    initAiEcosystemTab();
  }
})();
