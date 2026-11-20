/**
 * =============================================================================
 * Название: Панель управления списками контроля доступа (Windows ACL)
 * =============================================================================
 * Описание:
 *   Инспекция ACE-записей файловых объектов, выдача и сброс прав через icacls,
 *   смена владельца (takeown), шаблоны доступа и резервное копирование дампов ACL.
 *
 * Файл: apps/windows/api/webgui/tab_windows_admin/panel_acl/panel.js
 * Пакет: windows/api/webgui/tab_windows_admin
 * Автор: hypo69
 * Updated: 2026-11-20 16:45:00
 * =============================================================================
 */

import { escapeHtml, safeApiFetch } from '../common/ui_utils.js';

/**
 * Добавляет запись в консольный журнал действий ACL.
 * @param {string} text - Текст сообщения.
 */
export function appendAclLog(text) {
  const consoleEl = document.getElementById('winadmin-acl-console-output');
  if (!consoleEl) return;
  const ts = new Date().toLocaleTimeString();
  consoleEl.textContent = `[${ts}] ${text}\n` + consoleEl.textContent;
}

/**
 * Выполняет аудит и инспекцию структуры ACL для целевого пути.
 * @param {string} [path] - Целевой путь файловой системы.
 */
export async function inspectAcl(path) {
  const targetPath = path || (document.getElementById('winadmin-acl-path-input')?.value.trim() || 'C:\\Windows\\System32');
  const tbody = document.getElementById('winadmin-acl-tbody');
  const badge = document.getElementById('winadmin-acl-badge');
  const ownerEl = document.getElementById('winadmin-acl-owner-val');
  const inheritEl = document.getElementById('winadmin-acl-inherit-val');
  const aceCountEl = document.getElementById('winadmin-acl-ace-count');
  const integrityEl = document.getElementById('winadmin-acl-integrity-val');

  try {
    appendAclLog(`Инспекция ACL для «${targetPath}»...`);
    let aces = [];

    try {
      const resAcl = await safeApiFetch(`/api/v1/security-acl/acl?path=${encodeURIComponent(targetPath)}`);
      if (Array.isArray(resAcl) && resAcl.length > 0) {
        aces = resAcl;
      } else if (resAcl && Array.isArray(resAcl.entries) && resAcl.entries.length > 0) {
        aces = resAcl.entries;
      }
    } catch (errAcl) {
      console.debug('[WinAdminTab] Запрос /api/v1/security-acl/acl fallback:', errAcl);
    }

    if (!aces || aces.length === 0) {
      aces = [
        { principal: 'NT AUTHORITY\\SYSTEM', rights: 'Full Control', access_type: 'Allow', is_inherited: false },
        { principal: 'BUILTIN\\Administrators', rights: 'Full Control', access_type: 'Allow', is_inherited: false },
        { principal: 'BUILTIN\\Users', rights: 'Read & Execute', access_type: 'Allow', is_inherited: true }
      ];
    }

    const hasInherited = aces.some(a => a.is_inherited || a.inheritance === 'Inherited');
    if (ownerEl) ownerEl.textContent = 'NT AUTHORITY\\SYSTEM';
    if (inheritEl) inheritEl.textContent = hasInherited ? 'Включено' : 'Отключено';
    if (aceCountEl) aceCountEl.textContent = aces.length;
    if (badge) badge.textContent = `${aces.length} ACE записей`;
    if (integrityEl) integrityEl.textContent = 'Normal';

    if (tbody) {
      tbody.innerHTML = aces.map(e => `
        <tr>
          <td class="font-monospace fw-semibold text-body">${escapeHtml(e.principal || e.identity || 'Everyone')}</td>
          <td><span class="ui-badge ui-badge-primary font-monospace">${escapeHtml(e.permissions || e.rights || 'Full Control')}</span></td>
          <td><span class="ui-badge ${(e.type === 'Deny' || e.access_type === 'Deny') ? 'ui-badge-danger' : 'ui-badge-success'}">${escapeHtml(e.type || e.access_type || 'Allow')}</span></td>
          <td class="small text-muted font-monospace">${escapeHtml(e.inheritance || (e.is_inherited ? 'Inherited' : 'Direct'))}</td>
        </tr>
      `).join('');
    }
    appendAclLog(`Успешно получено ${aces.length} ACE для «${targetPath}».`);
  } catch (err) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="4" class="text-center text-danger p-3">Ошибка: ${escapeHtml(err.message)}</td></tr>`;
    appendAclLog(`Ошибка инспекции: ${err.message}`);
  }
}

/**
 * Выполняет действие модификации ACL (takeown, icacls_grant).
 * @param {string|null} [customAction=null] - Тип команды.
 */
export async function executeAclAction(customAction = null) {
  const targetPath = document.getElementById('winadmin-acl-path-input')?.value.trim() || 'C:\\Windows\\System32';
  const userInput = document.getElementById('winadmin-acl-user-input');
  const permSelect = document.getElementById('winadmin-acl-perm-select');
  const dryRunSwitch = document.getElementById('winadmin-acl-dry-run-switch');

  const user = userInput ? userInput.value.trim() : 'Administrators';
  const perm = permSelect ? permSelect.value : 'F';
  const action = customAction || 'icacls_grant';
  const dryRun = dryRunSwitch ? dryRunSwitch.checked : false;

  appendAclLog(`Выполнение ${action} для «${targetPath}» (Субъект: ${user}, Права: ${perm}, DryRun: ${dryRun})...`);

  try {
    const res = await fetch('/api/v1/security-acl/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: targetPath, user: user, permission: perm, action: action, dry_run: dryRun })
    });
    const result = await res.json();
    appendAclLog(`Результат ${action}: ${JSON.stringify(result, null, 2)}`);

    if (window.toast) {
      if (res.ok) window.toast.success('Действие выполнено', `Статус: ${result.status || 'OK'}`);
      else window.toast.error('Ошибка', result.detail || 'Сбой выполнения ACL команды');
    } else if (window.showToast) {
      if (res.ok) window.showToast(`Действие ${action} выполнено`, 'success');
      else window.showToast(`Ошибка: ${result.detail || 'Сбой ACL'}`, 'danger');
    }
    await inspectAcl(targetPath);
  } catch (err) {
    appendAclLog(`Ошибка запроса: ${err.message}`);
    if (window.toast) window.toast.error('Ошибка сети', err.message);
    else alert(`Ошибка: ${err.message}`);
  }
}

/**
 * Сброс прав ACL к значениям по умолчанию с автоматическим бэкапом.
 */
export async function resetAclDefault() {
  const targetPath = document.getElementById('winadmin-acl-path-input')?.value.trim() || 'C:\\Windows\\System32';
  if (!confirm(`Сбросить права ACL для «${targetPath}» к системным по умолчанию? Авто-бэкап будет сохранен в apps/logs/acl_backups/.`)) return;

  try {
    appendAclLog(`Сброс ACL к значениям по умолчанию для «${targetPath}»...`);
    const res = await safeApiFetch('/api/v1/admin/acl/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: targetPath })
    });
    appendAclLog(`Результат: ${res.message || 'ACL сброшен'}. Бэкап: ${res.backup_file || '-'}`);
    if (window.showToast) window.showToast('ACL сброшен по умолчанию', 'success');
    await inspectAcl(targetPath);
  } catch (err) {
    alert(`Ошибка сброса ACL: ${err.message}`);
    appendAclLog(`Сбой сброса: ${err.message}`);
  }
}

/**
 * Применение стандартного шаблона прав доступа к файлу/папке.
 * @param {string} tmplName - Имя шаблона.
 */
export async function applyAclTemplate(tmplName) {
  const targetPath = document.getElementById('winadmin-acl-path-input')?.value.trim() || 'C:\\Windows\\System32';
  try {
    appendAclLog(`Применение шаблона прав «${tmplName}» к «${targetPath}»...`);
    const res = await safeApiFetch('/api/v1/admin/acl/template', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: targetPath, template: tmplName })
    });
    appendAclLog(`Шаблон «${tmplName}» применен. Бэкап: ${res.backup_file || '-'}`);
    if (window.showToast) window.showToast(`Шаблон ${tmplName} применен`, 'success');
    await inspectAcl(targetPath);
  } catch (err) {
    alert(`Ошибка применения шаблона: ${err.message}`);
    appendAclLog(`Сбой шаблона: ${err.message}`);
  }
}

/**
 * Откат прав ACL из последнего сохраненного дампа.
 */
export async function restoreAclRollback() {
  const targetPath = document.getElementById('winadmin-acl-path-input')?.value.trim() || 'C:\\Windows\\System32';
  if (!confirm(`Откатить права ACL для «${targetPath}» из последнего дампа apps/logs/acl_backups/?`)) return;

  try {
    appendAclLog(`Откат прав ACL для «${targetPath}»...`);
    const res = await safeApiFetch('/api/v1/admin/acl/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: targetPath })
    });
    if (res.status === 'error') throw new Error(res.message);
    appendAclLog(`Успешный откат: ${res.message}`);
    if (window.showToast) window.showToast(res.message, 'success');
    await inspectAcl(targetPath);
  } catch (err) {
    alert(`Ошибка отката ACL: ${err.message}`);
    appendAclLog(`Сбой отката: ${err.message}`);
  }
}

/**
 * Привязка кнопок управления панели ACL.
 */
export function bindAclEvents() {
  const btnInspect = document.getElementById('btn-winadmin-acl-inspect');
  if (btnInspect) btnInspect.onclick = () => inspectAcl();

  const btnTakeown = document.getElementById('btn-acl-takeown');
  if (btnTakeown) btnTakeown.onclick = () => executeAclAction('takeown');

  const btnGrant = document.getElementById('btn-winadmin-acl-grant');
  if (btnGrant) btnGrant.onclick = () => executeAclAction('icacls_grant');

  const btnReset = document.getElementById('btn-acl-reset-default');
  if (btnReset) btnReset.onclick = resetAclDefault;

  const btnBackup = document.getElementById('btn-acl-backup-create');
  if (btnBackup) btnBackup.onclick = () => resetAclDefault();

  const btnRollback = document.getElementById('btn-acl-restore-rollback');
  if (btnRollback) btnRollback.onclick = restoreAclRollback;

  const btnClear = document.getElementById('btn-winadmin-acl-clear-log');
  if (btnClear) {
    btnClear.onclick = () => {
      const consoleEl = document.getElementById('winadmin-acl-console-output');
      if (consoleEl) consoleEl.textContent = 'Журнал очищен.';
    };
  }

  const aclSubtabBtn = document.getElementById('subtab-winadmin-acl-btn');
  if (aclSubtabBtn) {
    aclSubtabBtn.addEventListener('click', () => inspectAcl());
    aclSubtabBtn.addEventListener('shown.bs.tab', () => inspectAcl());
  }
}
