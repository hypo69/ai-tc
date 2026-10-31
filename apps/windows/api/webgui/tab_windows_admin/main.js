/**
 * =============================================================================
 * Название: Панель Windows Sysadmin & Identity - Главный оркестратор
 * =============================================================================
 * Описание:
 *   Главная точка входа и оркестратор модулей вкладки tab_windows_admin.
 *   Объединяет управление учетными записями, группами, журналами безопасности,
 *   аудитом прав, политиками SAM, инспектором процессов и ACL с поддержкой
 *   URL-маршрутизации панелей (#tab-windows-admin#<panel_id>).
 *
 * Файл: apps/windows/api/webgui/tab_windows_admin/main.js
 * Пакет: windows/api/webgui/tab_windows_admin
 * Автор: hypo69
 * Updated: 2026-10-28 19:04:00
 * =============================================================================
 */

import {
  fetchStatus,
  loadCurrentToken,
  updatePrivacyRadar,
  updateWindowsBackupStatus,
  triggerWindowsBackup
} from './panel_overview/panel.js';
import {
  fetchAccounts,
  filterUsersTable,
  openUserAiModal,
  handleCreateUserSubmit,
  deleteUserAction,
  setCurrentUserFilter,
  getCurrentUserFilter
} from './panel_users/panel.js';
import {
  loadGroups,
  filterGroupsTable,
  handleGroupRollover,
  viewGroupMembers
} from './panel_groups/panel.js';
import {
  loadSecurityEvents,
  applyEventsFilter,
  filterEventsTable,
  showEventDetail,
  setCurrentEventFilter
} from './panel_security_events/panel.js';
import {
  loadPasswordPolicy,
  runWhoIsAdminCheck,
  runServiceLogonCheck,
  runRdpCheck,
  runOrphanedCheck
} from './panel_audit_sam/panel.js';
import { handleExplainPid } from './panel_pid_inspector/panel.js';
import { loadCatalog, filterCatalogTable } from './panel_catalog/panel.js';
import {
  inspectAcl,
  executeAclAction,
  resetAclDefault,
  applyAclTemplate,
  restoreAclRollback,
  bindAclEvents
} from './panel_acl/panel.js';

export const TAB_ID = 'tab-windows-admin';
let isWinAdminInitialized = false;

/**
 * Проверяет, активна ли вкладка Windows Admin.
 * @returns {boolean}
 */
export function isWindowsAdminTabActive() {
  if (typeof document !== 'undefined' && document.hidden) return false;
  if (typeof window.isTabActive === 'function') {
    return Boolean(window.isTabActive(TAB_ID) || window.isTabActive('windows-admin') || window.isTabActive('accounts-identity'));
  }
  const pane = document.getElementById(TAB_ID) || document.getElementById('windows-admin');
  return pane ? pane.classList.contains('active') : false;
}

/**
 * Нормализует строковый идентификатор суб-вкладки.
 * @param {string} rawId - Сырой идентификатор вкладки.
 * @returns {string} Канонический идентификатор панели.
 */
export function normalizeSubTabId(rawId) {
  if (!rawId) return 'users';
  const s = String(rawId).toLowerCase().trim().replace(/^#/, '').replace(/^subtab-winadmin-/, '').replace(/-btn$/, '');
  if (s.includes('user') || s.includes('account')) return 'users';
  if (s.includes('group')) return 'groups';
  if (s.includes('event') || s.includes('log')) return 'events';
  if (s.includes('secur') || s.includes('policy') || s.includes('audit')) return 'security';
  if (s.includes('pid') || s.includes('proc')) return 'pid';
  if (s.includes('cat') || s.includes('soft')) return 'catalog';
  if (s.includes('acl') || s.includes('perm')) return 'acl';
  return s || 'users';
}

/**
 * Считывает суб-панель из URL hash.
 * @returns {string|null} ID субпанели или null.
 */
export function getPanelFromHash() {
  const hash = (typeof location !== 'undefined' ? location.hash : '') || '';
  if (!hash) return null;
  const cleanHash = hash.replace(/^#/, '');
  const parts = cleanHash.split('#');
  if (parts.length >= 2) {
    const mainPart = parts[0];
    if (mainPart === TAB_ID || mainPart === 'windows-admin' || mainPart === 'accounts-identity') {
      return normalizeSubTabId(parts[1]);
    }
  }
  return null;
}

/**
 * Обновляет адресную строку браузера активной суб-панелью (#tab-windows-admin#<panel_id>).
 * @param {string} panelId - Идентификатор панели.
 */
export function updateUrlWithPanel(panelId) {
  if (typeof history === 'undefined' || typeof location === 'undefined') return;
  const canonical = normalizeSubTabId(panelId);
  const search = location.search || '';
  const newHash = `#${TAB_ID}#${canonical}`;
  if (location.hash !== newHash) {
    try {
      history.replaceState(null, null, `${location.pathname}${search}${newHash}`);
    } catch (_) {}
  }
}

/**
 * Возвращает канонический идентификатор текущей активной субпанели.
 * @returns {string}
 */
export function getActiveSubTabId() {
  const activeBtn = document.querySelector('#winadmin-subtabs button.active');
  if (activeBtn) {
    const pId = activeBtn.getAttribute('data-panel-id');
    const target = activeBtn.getAttribute('data-bs-target') || '';
    return normalizeSubTabId(pId || target);
  }
  return getPanelFromHash() || 'users';
}

/**
 * Запрашивает API строго и исключительно для активной суб-панели.
 * Неактивные панели не запрашивают API.
 * @param {string} [subtabId] - Идентификатор целевой панели.
 */
export async function fetchActiveSubTabOnly(subtabId) {
  if (!isWindowsAdminTabActive()) return;
  const canonical = normalizeSubTabId(subtabId || getActiveSubTabId());
  switch (canonical) {
    case 'users':
      await fetchAccounts(getCurrentUserFilter());
      break;
    case 'groups':
      await loadGroups();
      break;
    case 'events':
      await loadSecurityEvents();
      break;
    case 'security':
      await loadPasswordPolicy();
      break;
    case 'pid':
      break;
    case 'catalog':
      await loadCatalog();
      break;
    case 'acl':
      await inspectAcl();
      break;
  }
}

/**
 * Переключение субвкладки панели Windows Sysadmin с обновлением URL.
 * @param {string} subtabName - Имя субвкладки ('users', 'groups', 'acl', etc.).
 * @param {boolean} [updateUrl=true] - Обновлять ли URL hash.
 */
export function switchWindowsAdminSubTab(subtabName, updateUrl = true) {
  const norm = normalizeSubTabId(subtabName);
  const btnId = `subtab-winadmin-${norm}-btn`;
  const btn = document.getElementById(btnId);
  if (btn && window.bootstrap) {
    new window.bootstrap.Tab(btn).show();
  } else if (btn) {
    btn.click();
  }

  if (updateUrl) {
    updateUrlWithPanel(norm);
  }
  fetchActiveSubTabOnly(norm);

  if (window.AISmartTooltip && typeof window.AISmartTooltip.initAll === 'function') {
    setTimeout(() => {
      window.AISmartTooltip.initAll(document.getElementById('windows-admin-root') || document);
    }, 100);
  }
}

/**
 * Обновление всех данных вкладки параллельно.
 */
export async function refreshAllData() {
  await Promise.allSettled([
    fetchStatus(),
    loadCurrentToken(),
    updatePrivacyRadar(),
    updateWindowsBackupStatus(),
    fetchActiveSubTabOnly(),
  ]);
}

/**
 * Привязка обработчиков событий элементов интерфейса.
 */
function bindEvents() {
  const refreshBtn = document.getElementById('btn-winadmin-refresh');
  if (refreshBtn) {
    refreshBtn.onclick = () => refreshAllData();
  }

  const openCreateUserBtn = document.getElementById('btn-open-create-user-modal');
  if (openCreateUserBtn) {
    openCreateUserBtn.onclick = () => {
      const modalEl = document.getElementById('createUserModal');
      if (modalEl && window.bootstrap) {
        const modal = new window.bootstrap.Modal(modalEl);
        modal.show();
      }
    };
  }

  const submitCreateUserBtn = document.getElementById('btn-submit-create-user');
  if (submitCreateUserBtn) {
    submitCreateUserBtn.onclick = handleCreateUserSubmit;
  }

  const filterGroup = document.getElementById('winadmin-user-filters');
  if (filterGroup) {
    filterGroup.querySelectorAll('.winadmin-filter-btn').forEach(btn => {
      btn.onclick = () => {
        filterGroup.querySelectorAll('.winadmin-filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const filter = btn.getAttribute('data-filter') || 'all';
        setCurrentUserFilter(filter);
        fetchAccounts(filter);
      };
    });
  }

  const filterUsersInput = document.getElementById('filter-users-input');
  if (filterUsersInput) {
    filterUsersInput.oninput = (e) => filterUsersTable(e.target.value);
  }

  const filterGroupsInput = document.getElementById('filter-groups-input');
  if (filterGroupsInput) {
    filterGroupsInput.oninput = (e) => filterGroupsTable(e.target.value);
  }

  const eventsFilterToolbar = document.getElementById('events-quick-filters');
  if (eventsFilterToolbar) {
    eventsFilterToolbar.querySelectorAll('.event-filter-btn').forEach(btn => {
      btn.onclick = () => {
        eventsFilterToolbar.querySelectorAll('.event-filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const filter = btn.getAttribute('data-filter') || 'all';
        setCurrentEventFilter(filter);
        applyEventsFilter();
      };
    });
  }

  const filterEventsInput = document.getElementById('filter-events-input');
  if (filterEventsInput) {
    filterEventsInput.oninput = () => filterEventsTable();
  }

  const refreshEventsBtn = document.getElementById('btn-refresh-events');
  if (refreshEventsBtn) {
    refreshEventsBtn.onclick = () => loadSecurityEvents();
  }

  const filterCatalogInput = document.getElementById('filter-catalog-input');
  if (filterCatalogInput) {
    filterCatalogInput.oninput = (e) => filterCatalogTable(e.target.value);
  }

  const btnWhoIsAdmin = document.getElementById('btn-check-who-is-admin');
  if (btnWhoIsAdmin) btnWhoIsAdmin.onclick = runWhoIsAdminCheck;

  const btnServiceLogon = document.getElementById('btn-check-service-logon');
  if (btnServiceLogon) btnServiceLogon.onclick = runServiceLogonCheck;

  const btnRdp = document.getElementById('btn-check-rdp');
  if (btnRdp) btnRdp.onclick = runRdpCheck;

  const btnOrphaned = document.getElementById('btn-check-orphaned');
  if (btnOrphaned) btnOrphaned.onclick = runOrphanedCheck;

  const btnExplainPid = document.getElementById('btn-explain-pid');
  if (btnExplainPid) btnExplainPid.onclick = handleExplainPid;

  // Навигация по суб-вкладкам меню
  const navContainer = document.getElementById('winadmin-subtabs');
  if (navContainer) {
    navContainer.querySelectorAll('button[data-bs-toggle="pill"]').forEach((btn) => {
      btn.addEventListener('shown.bs.tab', (e) => {
        const pId = e.target.getAttribute('data-panel-id') || normalizeSubTabId(e.target.id);
        updateUrlWithPanel(pId);
        fetchActiveSubTabOnly(pId);
      });
      btn.addEventListener('click', () => {
        const pId = btn.getAttribute('data-panel-id') || normalizeSubTabId(btn.id);
        updateUrlWithPanel(pId);
        fetchActiveSubTabOnly(pId);
      });
    });
  }

  // Слушатель изменения hash в URL при активной вкладке
  window.addEventListener('hashchange', () => {
    if (!isWindowsAdminTabActive()) return;
    const target = getPanelFromHash();
    if (target) {
      switchWindowsAdminSubTab(target, false);
    }
  });

  // Активация вкладки в общем интерфейсе
  document.addEventListener('tab:activated', (e) => {
    const tid = e.detail?.tabId;
    if (tid === TAB_ID || tid === 'windows-admin' || tid === 'accounts-identity') {
      const target = getPanelFromHash();
      if (target) {
        switchWindowsAdminSubTab(target, false);
      } else {
        updateUrlWithPanel('users');
      }
    }
  });

  if (window.registerTabPoller) {
    window.registerTabPoller('tab-windows-admin', async () => {
      if (window.isPanelActive && window.isPanelActive('tab-windows-admin', 'panel-overview', 'panel-overview')) {
        await updatePrivacyRadar();
        await updateWindowsBackupStatus();
      }
    }, 15000, { pollerId: 'winadmin_overview_poller', immediate: false });
  }
}

/**
 * Инициализация панели Windows Sysadmin & Identity.
 */
export async function initWindowsAdminTab() {
  console.log('[WinAdminTab] Инициализация панели Sysadmin & Identity...');

  if (!isWinAdminInitialized) {
    bindEvents();
    bindAclEvents();
    isWinAdminInitialized = true;
  }

  if (window.AISmartTooltip && typeof window.AISmartTooltip.initAll === 'function') {
    window.AISmartTooltip.initAll(document.getElementById('windows-admin-root') || document);
  }

  // Опрашиваем API ТОЛЬКО для активной панели
  await Promise.allSettled([
    fetchStatus(),
    loadCurrentToken(),
    updatePrivacyRadar(),
    updateWindowsBackupStatus(),
  ]);

  const activePanel = getPanelFromHash() || getActiveSubTabId() || 'users';
  if (getPanelFromHash()) {
    switchWindowsAdminSubTab(activePanel, false);
  } else {
    await fetchActiveSubTabOnly(activePanel);
  }
}

// Экспорт глобальных функций для вызова из внешних контейнеров и HTML
window.initWindowsAdminTab = initWindowsAdminTab;
window.initAccountsIdentityTab = initWindowsAdminTab;
window.activateWindowsAdminTab = function() {
  if (window.AISmartTooltip && typeof window.AISmartTooltip.initAll === 'function') {
    window.AISmartTooltip.initAll(document.getElementById('windows-admin-root') || document);
  }
};
window.triggerWindowsBackup = triggerWindowsBackup;
window.updateWindowsBackupStatus = updateWindowsBackupStatus;
window._explainUserDossier = openUserAiModal;
window._deleteUserAction = deleteUserAction;
window._handleGroupRollover = handleGroupRollover;
window._viewGroupMembers = viewGroupMembers;
window._showEventDetail = showEventDetail;
window.applyAclTemplate = applyAclTemplate;
window.inspectAcl = inspectAcl;
window.executeAclAction = executeAclAction;
window.resetAclDefault = resetAclDefault;
window.switchWindowsAdminSubTab = switchWindowsAdminSubTab;
window.getWindowsAdminPanelFromHash = getPanelFromHash;
window.updateWindowsAdminUrlWithPanel = updateUrlWithPanel;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initWindowsAdminTab);
} else {
  initWindowsAdminTab();
}
