/**
 * =============================================================================
 * Process Name: Windows Modules - Tab-Manager Script
 * =============================================================================
 * Description:
 *   Клиентский скрипт управления интерфейсом модуля tab-manager.
 *
 * Usage Examples:
 *   HTML Integration:
 *     <script src="/windows/api/webgui/admin/modules/tab-manager.js?v=20261001_v1" type="module"></script>
 *
 *   JavaScript Import:
 *     import { setupTabManagement, onTabSwitched } from '/windows/api/webgui/admin/modules/tab-manager.js';
 *
 * File: tab-manager.js
 * Project: ai-tc
 * Package: windows/api/webgui/admin/modules
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-11-13 16:10:00
 * =============================================================================
 */

/**
 * Tab Manager Module - Управление вкладками и навигацией
 */

export function setupTabManagement() {
  setupDropdownTabs();
  setupTabEvents();
}

function setupDropdownTabs() {
  const mainTabs = document.getElementById('mainTabs');
  if (!mainTabs) return;

  const dropdowns = mainTabs.querySelectorAll('.dropdown-toggle');

  // Поддержка onover (hover) для выпадающих меню навбара с таймером грации
  const dropdownWrappers = mainTabs.querySelectorAll('.dropdown');
  dropdownWrappers.forEach((dropdownEl) => {
    let hideTimer = null;

    const showDropdown = () => {
      clearTimeout(hideTimer);
      const menu = dropdownEl.querySelector('.dropdown-menu');
      const toggle = dropdownEl.querySelector('.dropdown-toggle');
      if (!menu) return;

      // Close other dropdowns
      document.querySelectorAll('#mainTabs .dropdown-menu.show').forEach((otherMenu) => {
        if (otherMenu !== menu) {
          otherMenu.classList.remove('show');
          otherMenu.closest('.dropdown')?.querySelector('.dropdown-toggle')?.classList.remove('show');
        }
      });

      menu.classList.add('show');
      if (toggle) toggle.classList.add('show');
    };

    const hideDropdown = () => {
      hideTimer = setTimeout(() => {
        const menu = dropdownEl.querySelector('.dropdown-menu');
        const toggle = dropdownEl.querySelector('.dropdown-toggle');
        if (menu) menu.classList.remove('show');
        if (toggle) toggle.classList.remove('show');
      }, 200);
    };

    dropdownEl.addEventListener('mouseenter', showDropdown);
    dropdownEl.addEventListener('mouseleave', hideDropdown);
  });

  dropdowns.forEach((dropdown) => {
    dropdown.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();

      const parentDropdown = dropdown.closest('.dropdown');
      const menu = dropdown.nextElementSibling || parentDropdown?.querySelector('.dropdown-menu');
      const isAlreadyOpen = menu?.classList.contains('show');

      // Close other dropdowns
      document.querySelectorAll('#mainTabs .dropdown-menu.show').forEach((otherMenu) => {
        otherMenu.classList.remove('show');
        otherMenu.closest('.dropdown')?.querySelector('.dropdown-toggle')?.classList.remove('show');
      });

      // Toggle current dropdown
      if (!isAlreadyOpen && menu) {
        dropdown.classList.add('show');
        menu.classList.add('show');
      }
    });
  });

  // Handle all clickable navigation items inside mainTabs (tabs and dropdown items)
  mainTabs.querySelectorAll('.dropdown-item, .list-group-item, [data-tab], [data-bs-target], [data-plugin]').forEach((item) => {
    // Поддержка onover для пунктов меню: фокус и подсветка на всю кнопку
    item.addEventListener('mouseenter', () => {
      item.focus({ preventScroll: true });
    });

    item.addEventListener('click', (e) => {
      const button = e.target.closest('.dropdown-item, .list-group-item, [data-tab], [data-bs-target], [data-plugin]') || item;
      const pluginName = button.getAttribute('data-plugin') || item.getAttribute('data-plugin');
      const targetId = button.getAttribute('data-tab') || 
                      button.getAttribute('data-bs-target')?.replace('#', '') ||
                      item.getAttribute('data-tab') || 
                      item.getAttribute('data-bs-target')?.replace('#', '');

      // Close parent dropdown menu
      const menu = button.closest('.dropdown-menu') || item.closest('.dropdown-menu');
      if (menu) {
        menu.classList.remove('show');
        menu.closest('.dropdown')?.querySelector('.dropdown-toggle')?.classList.remove('show');
      }

      if (pluginName && typeof window.openPluginFromDropdown === 'function') {
        e.preventDefault();
        e.stopPropagation();
        window.openPluginFromDropdown(pluginName);
      } else if (targetId) {
        e.preventDefault();
        e.stopPropagation();
        if (typeof window.switchTab === 'function') {
          window.switchTab(targetId);
        }
      }
    });
  });

  // Close dropdowns on outside click
  document.addEventListener('click', (e) => {
    if (!mainTabs.contains(e.target)) {
      dropdowns.forEach((dropdown) => {
        dropdown.classList.remove('show');
        const menu = dropdown.nextElementSibling;
        if (menu) menu.classList.remove('show');
      });
    }
  });
}

function setupTabEvents() {
  // Tab content click handlers
  const tabPane = document.getElementById('mainTabsContent');
  if (tabPane) {
    tabPane.addEventListener('click', (e) => {
      const target = e.target.closest('[data-tab]');
      if (target) {
        const tabId = target.getAttribute('data-tab');
        if (tabId) {
          window.switchTab(tabId);
        }
      }
    });
  }
}

export function onTabSwitched(targetId) {
  const cleanId = targetId.startsWith('#') ? targetId.slice(1) : targetId;
  
  if (cleanId === 'tab-chat') {
    if (typeof window.initChatTab === 'function') {
      window.initChatTab();
    }
  }
}

export { setupDropdownTabs, setupTabEvents };
