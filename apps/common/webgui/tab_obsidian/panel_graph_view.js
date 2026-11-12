/**
 * =============================================================================
 * Process Name: Common WebGUI - Obsidian Interactive 2D Graph View
 * =============================================================================
 * Description:
 *   Модуль интерактивной 2D-визуализации графа связей базы знаний Obsidian
 *   (apps/common/webgui/tab_obsidian).
 *   Обеспечивает отрисовку узлов (заметок), ребер (связей), масштабирование,
 *   панорамирование (pan & zoom) и переход к заметке по клику на узел.
 *
 * File: panel_graph_view.js
 * Project: ai-assistant
 * Package: apps.common.webgui.tab_obsidian
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-30 16:45:00
 * =============================================================================
 */

let graphScale = 1;
let graphPan = { x: 0, y: 0 };
let isDraggingCanvas = false;
let dragStart = { x: 0, y: 0 };
let currentGraphData = { nodes: [], links: [] };

export async function fetchAndRenderGraph(activeNotePath, onNodeSelect) {
  const canvas = document.getElementById('obs-graph-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  canvas.width = canvas.parentElement.clientWidth || 800;
  canvas.height = canvas.parentElement.clientHeight || 600;

  try {
    const res = await fetch('/api/v1/obsidian/graph');
    if (!res.ok) return;
    currentGraphData = await res.json();
  } catch (err) {
    console.warn('[ObsidianGraph] Ошибка загрузки графа:', err);
    return;
  }

  const cx = canvas.width / 2;
  const cy = canvas.height / 2;
  const r = Math.min(cx, cy) * 0.75;
  const total = currentGraphData.nodes.length;

  currentGraphData.nodes.forEach((node, i) => {
    const angle = (i / Math.max(1, total)) * 2 * Math.PI;
    node.x = cx + r * Math.cos(angle) + (Math.random() - 0.5) * 40;
    node.y = cy + r * Math.sin(angle) + (Math.random() - 0.5) * 40;
  });

  drawCanvas(ctx, canvas, activeNotePath);

  // Обработчики масштабирования и управления
  const btnIn = document.getElementById('obs-graph-zoom-in');
  const btnOut = document.getElementById('obs-graph-zoom-out');
  const btnReset = document.getElementById('obs-graph-zoom-reset');

  if (btnIn) btnIn.onclick = () => { graphScale *= 1.2; drawCanvas(ctx, canvas, activeNotePath); };
  if (btnOut) btnOut.onclick = () => { graphScale /= 1.2; drawCanvas(ctx, canvas, activeNotePath); };
  if (btnReset) btnReset.onclick = () => { graphScale = 1; graphPan = { x: 0, y: 0 }; drawCanvas(ctx, canvas, activeNotePath); };

  canvas.onmousedown = (e) => {
    isDraggingCanvas = true;
    dragStart = { x: e.clientX - graphPan.x, y: e.clientY - graphPan.y };
  };

  window.onmousemove = (e) => {
    if (isDraggingCanvas) {
      graphPan.x = e.clientX - dragStart.x;
      graphPan.y = e.clientY - dragStart.y;
      drawCanvas(ctx, canvas, activeNotePath);
    }
  };

  window.onmouseup = () => { isDraggingCanvas = false; };

  canvas.onclick = (e) => {
    const rect = canvas.getBoundingClientRect();
    const clickX = (e.clientX - rect.left - graphPan.x) / graphScale;
    const clickY = (e.clientY - rect.top - graphPan.y) / graphScale;

    for (const node of currentGraphData.nodes) {
      const dist = Math.hypot(node.x - clickX, node.y - clickY);
      if (dist <= Math.max(12, node.val * 3)) {
        if (typeof onNodeSelect === 'function') {
          onNodeSelect(node.id);
        }
        break;
      }
    }
  };
}

function drawCanvas(ctx, canvas, activeNotePath) {
  ctx.save();
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.translate(graphPan.x, graphPan.y);
  ctx.scale(graphScale, graphScale);

  const nodeMap = new Map();
  currentGraphData.nodes.forEach(n => nodeMap.set(n.id, n));

  // Отрисовка связей
  ctx.lineWidth = 1;
  ctx.strokeStyle = 'rgba(128, 128, 128, 0.35)';
  currentGraphData.links.forEach(l => {
    const src = nodeMap.get(l.source);
    const tgt = nodeMap.get(l.target);
    if (src && tgt) {
      ctx.beginPath();
      ctx.moveTo(src.x, src.y);
      ctx.lineTo(tgt.x, tgt.y);
      ctx.stroke();
    }
  });

  // Отрисовка узлов
  currentGraphData.nodes.forEach(node => {
    const radius = Math.max(8, Math.min(24, node.val * 2.5));
    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
    ctx.fillStyle = node.id === activeNotePath ? 'var(--bs-primary, #0d6efd)' : '#6c757d';
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    ctx.font = '11px sans-serif';
    ctx.fillStyle = node.id === activeNotePath ? 'var(--bs-primary, #0d6efd)' : '#888888';
    ctx.textAlign = 'center';
    ctx.fillText(node.label, node.x, node.y + radius + 14);
  });

  ctx.restore();
}
