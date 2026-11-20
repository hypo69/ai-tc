/**
 * Модуль управления и запуска пошаговой AI-диагностики системы.
 * Файл: apps/windows/api/webgui/tab_about_system/panel_ai_diagnostics/panel.js
 * Updated: 2026-11-12 12:40:00
 */

import { apiFetch, escapeHtml } from '../common/ui_utils.js';
import { renderAIDiagnosticStages, renderAIDomainCards } from './renderers.js';

let isAiRunning = false;

/**
 * Инициализирует панель AI-диагностики и привязывает обработчики событий кнопок.
 */
export function initAIDiagnosticsPanel() {
  bindAIEvents();
}

/**
 * Привязывает обработчики событий к элементам управления панели AI-диагностики.
 */
export function bindAIEvents() {
  const btnRescan = document.getElementById('btn-about-ai-rescan');
  if (btnRescan) {
    btnRescan.onclick = () => runAIDiagnostics(true);
  }

  const btnToggleStages = document.getElementById('btn-about-ai-toggle-stages');
  const stagesBox = document.getElementById('about-ai-stages-container');
  const icStages = document.getElementById('ic-about-ai-toggle-stages');
  const txtStages = document.getElementById('txt-about-ai-toggle-stages');
  if (btnToggleStages && stagesBox) {
    btnToggleStages.onclick = () => {
      const isHidden = stagesBox.classList.toggle('d-none');
      if (icStages) {
        icStages.className = isHidden ? 'bi bi-chevron-down ms-0.5' : 'bi bi-chevron-up ms-0.5';
      }
      if (txtStages) {
        txtStages.textContent = isHidden ? 'Показать этапы' : 'Свернуть этапы';
      }
    };
  }

  const btnToggleInstruction = document.getElementById('btn-about-ai-toggle-instruction');
  const instructionCollapse = document.getElementById('about-ai-instruction-collapse');
  const icInstruction = document.getElementById('ic-about-ai-instruction');
  if (btnToggleInstruction && instructionCollapse) {
    btnToggleInstruction.onclick = () => {
      const isShown = !instructionCollapse.classList.toggle('d-none');
      if (icInstruction) {
        icInstruction.className = isShown ? 'bi bi-chevron-up text-muted ms-1' : 'bi bi-chevron-down text-muted ms-1';
      }
    };
  }

  const btnCopyInstruction = document.getElementById('btn-about-ai-copy-instruction');
  if (btnCopyInstruction) {
    btnCopyInstruction.onclick = () => {
      const text = document.getElementById('about-ai-instruction-text')?.textContent || '';
      navigator.clipboard.writeText(text).then(() => {
        const s = document.getElementById('txt-about-ai-copy-instruction');
        if (s) s.textContent = 'Скопировано!';
        setTimeout(() => { if (s) s.textContent = 'Копировать'; }, 1800);
      });
    };
  }

  const btnTogglePrompt = document.getElementById('btn-about-ai-toggle-prompt');
  const promptCollapse = document.getElementById('about-ai-prompt-collapse');
  const icPrompt = document.getElementById('ic-about-ai-prompt');
  if (btnTogglePrompt && promptCollapse) {
    btnTogglePrompt.onclick = () => {
      const isShown = !promptCollapse.classList.toggle('d-none');
      if (icPrompt) {
        icPrompt.className = isShown ? 'bi bi-chevron-up text-muted ms-1' : 'bi bi-chevron-down text-muted ms-1';
      }
    };
  }

  const btnCopyPrompt = document.getElementById('btn-about-ai-copy-prompt');
  if (btnCopyPrompt) {
    btnCopyPrompt.onclick = () => {
      const text = document.getElementById('about-ai-prompt-text')?.textContent || '';
      navigator.clipboard.writeText(text).then(() => {
        const s = document.getElementById('txt-about-ai-copy-prompt');
        if (s) s.textContent = 'Скопировано!';
        setTimeout(() => { if (s) s.textContent = 'Копировать'; }, 1800);
      });
    };
  }

  const btnToggleRaw = document.getElementById('btn-about-ai-toggle-raw');
  const rawCollapse = document.getElementById('about-ai-raw-collapse');
  const icRaw = document.getElementById('ic-about-ai-raw');
  if (btnToggleRaw && rawCollapse) {
    btnToggleRaw.onclick = () => {
      const isShown = !rawCollapse.classList.toggle('d-none');
      if (icRaw) {
        icRaw.className = isShown ? 'bi bi-chevron-up text-muted ms-1' : 'bi bi-chevron-down text-muted ms-1';
      }
    };
  }

  const btnCopyRaw = document.getElementById('btn-about-ai-copy-raw');
  if (btnCopyRaw) {
    btnCopyRaw.onclick = () => {
      const text = document.getElementById('about-ai-raw-text')?.textContent || '';
      navigator.clipboard.writeText(text).then(() => {
        const s = document.getElementById('txt-about-ai-copy-raw');
        if (s) s.textContent = 'Скопировано!';
        setTimeout(() => { if (s) s.textContent = 'Копировать'; }, 1800);
      });
    };
  }

  const btnToggleSnapshot = document.getElementById('btn-about-ai-toggle-snapshot');
  const snapshotCollapse = document.getElementById('about-ai-snapshot-collapse');
  const icSnapshot = document.getElementById('ic-about-ai-snapshot');
  if (btnToggleSnapshot && snapshotCollapse) {
    btnToggleSnapshot.onclick = () => {
      const isShown = !snapshotCollapse.classList.toggle('d-none');
      if (icSnapshot) {
        icSnapshot.className = isShown ? 'bi bi-chevron-up text-muted ms-1' : 'bi bi-chevron-down text-muted ms-1';
      }
    };
  }

  const btnCopySnapshot = document.getElementById('btn-about-ai-copy-snapshot');
  if (btnCopySnapshot) {
    btnCopySnapshot.onclick = () => {
      const text = document.getElementById('about-ai-snapshot-text')?.textContent || '';
      navigator.clipboard.writeText(text).then(() => {
        const s = document.getElementById('txt-about-ai-copy-snapshot');
        if (s) s.textContent = 'Скопировано!';
        setTimeout(() => { if (s) s.textContent = 'Копировать JSON'; }, 1800);
      });
    };
  }
}

/**
 * Запускает пошаговую AI-диагностику хоста и выводит результаты по доменам.
 * @param {boolean} [isManualRescan=false] - Флаг ручного перезапуска.
 */
export async function runAIDiagnostics(isManualRescan = false) {
  if (isAiRunning) return;
  isAiRunning = true;

  if (window.setTabProcessing) {
    window.setTabProcessing('tab-about-system', true);
  }

  const btnRescan = document.getElementById('btn-about-ai-rescan');
  const txtRescan = document.getElementById('txt-about-ai-rescan');
  const icRescan = document.getElementById('ic-about-ai-rescan');
  const badgeHealth = document.getElementById('about-ai-health-badge');
  const badgeHealthBtn = document.getElementById('about-ai-health-badge-btn');
  const engineTag = document.getElementById('about-ai-engine-name');
  const summaryEl = document.getElementById('about-ai-summary-text');
  const errorSec = document.getElementById('about-ai-error-section');
  const errorText = document.getElementById('about-ai-error-text');
  const progressBar = document.getElementById('about-ai-step-progress');
  const synthesisStatus = document.getElementById('about-ai-synthesis-status');
  const actionsBox = document.getElementById('about-ai-actions-box');
  const actionsList = document.getElementById('about-ai-actions-list');
  const instructionText = document.getElementById('about-ai-instruction-text');
  const promptText = document.getElementById('about-ai-prompt-text');
  const rawText = document.getElementById('about-ai-raw-text');

  const liveStatusText = document.getElementById('about-ai-live-status-text');
  const chipWmi = document.getElementById('chip-sensor-wmi');
  const chipRam = document.getElementById('chip-sensor-ram');
  const chipDisks = document.getElementById('chip-sensor-disks');
  const chipNet = document.getElementById('chip-sensor-net');
  const snapshotText = document.getElementById('about-ai-snapshot-text');
  const tickCpu = document.getElementById('live-tick-cpu');
  const tickTemp = document.getElementById('live-tick-temp');
  const tickRam = document.getElementById('live-tick-ram');
  const tickDisks = document.getElementById('live-tick-disks');
  const tickTopProc = document.getElementById('live-tick-top-proc');

  if (btnRescan) btnRescan.disabled = true;
  if (icRescan) icRescan.className = 'spinner-border spinner-border-sm text-dark';
  if (txtRescan) txtRescan.textContent = 'Диагностика...';

  if (errorSec) errorSec.classList.add('d-none');
  if (actionsBox) actionsBox.classList.add('d-none');
  if (progressBar) progressBar.style.width = '5%';

  if (liveStatusText) liveStatusText.textContent = 'Опрос системных датчиков хоста (WMI, CIM, psutil, SMART)...';

  [chipWmi, chipRam, chipDisks, chipNet].forEach(c => {
    if (c) c.className = 'badge bg-secondary bg-opacity-40 text-light border border-secondary';
  });

  if (badgeHealth) {
    badgeHealth.textContent = 'Health: Поэтапный опрос...';
    badgeHealth.className = 'badge bg-warning-subtle text-warning border border-warning font-monospace';
  }
  if (badgeHealthBtn) {
    badgeHealthBtn.textContent = 'Health: Опрос...';
    badgeHealthBtn.className = 'badge bg-warning-subtle text-warning border border-warning font-monospace ms-1';
  }

  const stagesLog = [
    {
      stage: 'init',
      title: 'Сбор телеметрии',
      message: '🔌 Получение среза телеметрии и сенсоров хоста...',
      details: 'Опрос системных WMI/CIM счетчиков, psutil и SystemSnapshot',
    }
  ];
  renderAIDiagnosticStages(stagesLog, false);

  try {
    const groups = await apiFetch('/api/v1/system/diagnose/groups');
    if (!Array.isArray(groups) || groups.length === 0) {
      throw new Error('Не удалось получить список диагностических групп');
    }

    if (snapshotText) {
      snapshotText.textContent = JSON.stringify(groups, null, 2);
    }

    const compGroup = groups.find(g => g.group_id === 'compute_thermals');
    if (compGroup && compGroup.payload) {
      const cpu = compGroup.payload.cpu || {};
      if (tickCpu) tickCpu.textContent = `${cpu.model || 'CPU'} (${cpu.load_percent ?? 0}%)`;
      const temps = compGroup.payload.sensors?.temperatures_celsius || {};
      const tempVals = Object.values(temps);
      const maxT = tempVals.length > 0 ? Math.max(...tempVals) : null;
      if (tickTemp) tickTemp.textContent = maxT !== null ? `${maxT}°C` : 'В норме';
    }

    const memGroup = groups.find(g => g.group_id === 'memory_processes');
    if (memGroup && memGroup.payload) {
      const ram = memGroup.payload.ram || {};
      if (tickRam) tickRam.textContent = `${ram.used_gb ?? 0} / ${ram.total_gb ?? 0} GB (${ram.used_percent ?? 0}%)`;
      const procs = memGroup.payload.top_active_processes || [];
      if (tickTopProc) tickTopProc.textContent = procs.length > 0 ? `${procs[0].name} (${procs[0].cpu_percent ?? 0}%)` : 'Нет активных';
    }

    const diskGroup = groups.find(g => g.group_id === 'storage_smart');
    if (diskGroup && diskGroup.payload) {
      const parts = diskGroup.payload.storage_partitions || [];
      if (tickDisks) tickDisks.textContent = parts.map(p => {
        const title = p.volume_name ? `${p.volume_name} (${p.mountpoint || p.device || ''})` : (p.mountpoint || p.device || 'Vol');
        return `${title}: ${p.free_gb ?? 0} GB св.`;
      }).join(', ') || 'OK';
    }

    const cardsState = groups.map(g => {
      const keyMetrics = {};
      if (g.group_id === 'compute_thermals') {
        const cpu = g.payload?.cpu || {};
        keyMetrics['cpu_load'] = `${cpu.load_percent ?? 0}%`;
        keyMetrics['cpu_model'] = cpu.model || 'CPU';
        const temps = g.payload?.sensors?.temperatures_celsius || {};
        const maxT = Object.values(temps).length > 0 ? Math.max(...Object.values(temps)) : null;
        keyMetrics['max_temp'] = maxT !== null ? `${maxT}°C` : 'В норме';
      } else if (g.group_id === 'memory_processes') {
        const ram = g.payload?.ram || {};
        keyMetrics['ram_used'] = `${ram.used_gb ?? 0} / ${ram.total_gb ?? 0} GB (${ram.used_percent ?? 0}%)`;
        const procs = g.payload?.top_active_processes || [];
        keyMetrics['top_process'] = procs.length > 0 ? `${procs[0].name} (${procs[0].cpu_percent ?? 0}%)` : 'Нет';
      } else if (g.group_id === 'storage_smart') {
        const parts = g.payload?.storage_partitions || [];
        const maxUsed = parts.length > 0 ? Math.max(...parts.map(p => p.used_percent || 0)) : 0;
        keyMetrics['max_volume_fill'] = `${maxUsed}%`;
        keyMetrics['volumes_count'] = parts.length;
      } else if (g.group_id === 'system_network') {
        const updates = g.payload?.system_updates || {};
        keyMetrics['reboot_pending'] = updates.reboot_pending ? 'Да' : 'Нет';
        keyMetrics['update_status'] = updates.status || 'Up to date';
      }

      return {
        group_id: g.group_id,
        title: g.title,
        icon: g.icon,
        status: 'pending',
        summary: g.description,
        key_metrics: keyMetrics,
        payload: g.payload,
      };
    });
    renderAIDomainCards(cardsState);

    const completedGroups = [];

    for (let i = 0; i < groups.length; i++) {
      const group = groups[i];
      const stepNum = i + 1;
      const totalSteps = groups.length;
      const pct = Math.round((stepNum / totalSteps) * 85);
      if (progressBar) progressBar.style.width = `${pct}%`;

      if (group.group_id === 'compute_thermals') {
        if (chipWmi) chipWmi.className = 'badge bg-info text-dark border border-info fw-bold';
      } else if (group.group_id === 'memory_processes') {
        if (chipRam) chipRam.className = 'badge bg-info text-dark border border-info fw-bold';
      } else if (group.group_id === 'storage_smart') {
        if (chipDisks) chipDisks.className = 'badge bg-info text-dark border border-info fw-bold';
      } else if (group.group_id === 'system_network') {
        if (chipNet) chipNet.className = 'badge bg-info text-dark border border-info fw-bold';
      }

      if (liveStatusText) {
        liveStatusText.textContent = `🧠 Анализ [${stepNum}/${totalSteps}]: ${group.title} (оценка сенсоров и метрик)...`;
      }

      cardsState[i].status = 'analyzing';
      cardsState[i].summary = `🧠 Модель выполняет целевой анализ телеметрии группы ${stepNum}/${totalSteps}...`;
      renderAIDomainCards(cardsState);

      stagesLog.push({
        stage: 'group_run',
        title: `Группа ${stepNum}/${totalSteps}`,
        message: `🧠 [${stepNum}/${totalSteps}] Запрос модели: ${group.title}...`,
        details: group.description,
      });
      renderAIDiagnosticStages(stagesLog, false);

      const res = await apiFetch('/api/v1/system/diagnose/group', {
        method: 'POST',
        body: JSON.stringify({
          group_id: group.group_id,
          title: group.title,
          payload: group.payload,
        }),
      });

      if (res) {
        cardsState[i] = res;
        completedGroups.push(res);

        if (promptText && res.generated_prompt) {
          promptText.textContent = `[${res.title}]\n${res.generated_prompt}`;
        }
        if (instructionText && res.system_instruction) {
          instructionText.textContent = res.system_instruction;
        }
        if (rawText && res.raw_response) {
          rawText.textContent = `[${res.title}]\n${res.raw_response}`;
        }
      } else {
        cardsState[i].status = 'warning';
        cardsState[i].summary = 'Ответ не получен, используются базовые метрики.';
        completedGroups.push(cardsState[i]);
      }

      if (group.group_id === 'compute_thermals') {
        if (chipWmi) chipWmi.className = 'badge bg-success-subtle text-success border border-success';
      } else if (group.group_id === 'memory_processes') {
        if (chipRam) chipRam.className = 'badge bg-success-subtle text-success border border-success';
      } else if (group.group_id === 'storage_smart') {
        if (chipDisks) chipDisks.className = 'badge bg-success-subtle text-success border border-success';
      } else if (group.group_id === 'system_network') {
        if (chipNet) chipNet.className = 'badge bg-success-subtle text-success border border-success';
      }

      renderAIDomainCards(cardsState);

      stagesLog.push({
        stage: 'group_done',
        title: `Группа ${stepNum} завершена`,
        message: `✅ [${stepNum}/${totalSteps}] ${group.title}: ${cardsState[i].status.toUpperCase()}`,
        details: cardsState[i].summary.substring(0, 120) + (cardsState[i].summary.length > 120 ? '...' : ''),
      });
      renderAIDiagnosticStages(stagesLog, false);
    }

    if (liveStatusText) {
      liveStatusText.textContent = '🏆 Поэтапный опрос и анализ всех доменов завершен.';
    }

    if (progressBar) progressBar.style.width = '95%';
    stagesLog.push({
      stage: 'synthesis',
      title: 'Финальный синтез',
      message: '🏆 Формирование итогового заключения и расчет Health Score...',
      details: 'Агрегация заключений всех 4 доменов',
    });
    renderAIDiagnosticStages(stagesLog, false);

    const synthesis = await apiFetch('/api/v1/system/diagnose/synthesize', {
      method: 'POST',
      body: JSON.stringify({ groups: completedGroups }),
    });

    if (progressBar) progressBar.style.width = '100%';

    if (synthesis) {
      if (promptText && synthesis.generated_prompt) {
        promptText.textContent = `[Синтез итогового заключения]\n${synthesis.generated_prompt}`;
      }
      if (instructionText && synthesis.system_instruction) {
        instructionText.textContent = synthesis.system_instruction;
      }
      if (rawText && synthesis.raw_response) {
        rawText.textContent = `[Синтез]\n${synthesis.raw_response}`;
      }
    }

    const score = Number(synthesis?.health_score || 100);
    const healthClass = score >= 80 ? 'bg-success-subtle text-success border border-success' :
      score >= 60 ? 'bg-warning-subtle text-warning border border-warning' :
      'bg-danger-subtle text-danger border border-danger';

    if (badgeHealth) {
      badgeHealth.textContent = `Health: ${score}/100`;
      badgeHealth.className = `badge font-monospace ${healthClass}`;
    }
    if (badgeHealthBtn) {
      badgeHealthBtn.textContent = `Health: ${score}/100`;
      badgeHealthBtn.className = `badge font-monospace ms-1 ${healthClass}`;
    }

    if (engineTag) {
      engineTag.innerHTML = `<i class="bi bi-cpu me-1"></i>${escapeHtml(synthesis?.ai_model_used || 'Heuristic Engine')}`;
    }

    if (synthesisStatus) {
      synthesisStatus.textContent = `${synthesis?.status_label || 'OK'} (${score}/100)`;
      synthesisStatus.className = `badge font-monospace ${
        score >= 80 ? 'bg-success' :
        score >= 60 ? 'bg-warning' :
        'bg-danger'
      }`;
    }

    if (summaryEl) {
      summaryEl.textContent = synthesis?.executive_summary || 'Анализ завершён.';
    }

    if (Array.isArray(synthesis?.critical_actions) && synthesis.critical_actions.length > 0) {
      if (actionsBox && actionsList) {
        actionsBox.classList.remove('d-none');
        actionsList.innerHTML = synthesis.critical_actions.map(act => `<li class="mb-1"><i class="bi bi-arrow-right-short text-warning me-1"></i>${escapeHtml(act)}</li>`).join('');
      }
    }

    stagesLog.push({
      stage: 'done',
      title: 'Аудит завершен',
      message: `✅ Поэтапная AI-диагностика успешно завершена (Health: ${score}/100)`,
      details: 'Все 4 функциональные группы оценены моделью',
    });
    renderAIDiagnosticStages(stagesLog, true);

  } catch (e) {
    console.error('[AboutSystemTab] Grouped AI Diagnosis error:', e);
    if (summaryEl) summaryEl.textContent = 'Ошибка выполнения поэтапной AI-диагностики: ' + e.message;
    if (badgeHealth) {
      badgeHealth.textContent = 'Health: Error';
      badgeHealth.className = 'badge bg-danger-subtle text-danger border border-danger font-monospace';
    }
    if (badgeHealthBtn) {
      badgeHealthBtn.textContent = 'Health: Error';
      badgeHealthBtn.className = 'badge bg-danger-subtle text-danger border border-danger font-monospace ms-1';
    }
    if (errorSec) {
      errorSec.classList.remove('d-none');
      if (errorText) errorText.textContent = e.message;
    }
    stagesLog.push({
      stage: 'error',
      title: 'Ошибка',
      message: `❌ Ошибка выполнения: ${e.message}`,
      details: 'Проверьте доступность API-сервера',
    });
    renderAIDiagnosticStages(stagesLog, true);
  } finally {
    isAiRunning = false;
    
    if (window.resetTabProcessing) {
      window.resetTabProcessing('tab-about-system');
    }
    
    if (btnRescan) btnRescan.disabled = false;
    if (icRescan) icRescan.className = 'bi bi-lightning-charge-fill';
    if (txtRescan) txtRescan.textContent = 'Rescan';
  }
}
