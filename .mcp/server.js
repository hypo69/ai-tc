/**
 * =============================================================================
 * Process Name: Auxiliary HTTP Pre-Commit and File Apply Server (server.js)
 * =============================================================================
 * Description:
 *   Lightweight Node.js Express server providing REST endpoints (/precommit, /apply)
 *   for safe automated Git commits and controlled workspace file updates.
 *
 * Examples:
 *   // POST /precommit { "message": "chore: save state" }
 *   // POST /apply { "filePath": "README.md", "content": "# Updated" }
 *
 * File: server.js
 * Module: MCP-Node-Server
 * Class: McpHttpBridge
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-31 17:07:00
 * =============================================================================
 */

const express = require('express');
const bodyParser = require('body-parser');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..');
const CONFIG_PATH = path.join(REPO_ROOT, 'config.json');

/**
 * Reads the root config.json file safely.
 *
 * @returns {Object} Parsed configuration object or empty object on failure.
 */
function loadProjectConfig() {
  if (!fs.existsSync(CONFIG_PATH)) {
    return {};
  }
  try {
    const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
    return JSON.parse(raw) ?? {};
  } catch {
    return {};
  }
}

/**
 * Resolves the server port from environment variables or config.json.
 *
 * @returns {number} Configured TCP port number.
 */
function resolvePort() {
  const envPort = Number(process.env.MCP_HTTP_PORT ?? process.env.PORT ?? 0);
  if (envPort > 0) {
    return envPort;
  }
  const cfg = loadProjectConfig();
  const cfgPort = Number(cfg?.mcp?.http_port ?? cfg?.server?.mcp_port ?? 0);
  return cfgPort > 0 ? cfgPort : Number(cfg?.server?.port ?? 8001) + 100;
}

/**
 * Executes a git command safely using argument arrays inside REPO_ROOT.
 *
 * @param {string[]} args - Array of git CLI arguments.
 * @returns {string} Standard output from git execution.
 */
function runGit(args) {
  return execFileSync('git', args, { cwd: REPO_ROOT, encoding: 'utf8' });
}

/**
 * Validates that a target path stays strictly inside REPO_ROOT.
 *
 * @param {string} relativeFilePath - Relative path requested by client.
 * @returns {string} Resolved absolute path inside REPO_ROOT, or empty string if invalid.
 */
function resolveSafeRepoPath(relativeFilePath) {
  if (!relativeFilePath || typeof relativeFilePath !== 'string') {
    return '';
  }
  const resolved = path.resolve(REPO_ROOT, relativeFilePath);
  const normalizedRoot = path.resolve(REPO_ROOT) + path.sep;
  if (!resolved.startsWith(normalizedRoot)) {
    return '';
  }
  return resolved;
}

const app = express();
app.use(bodyParser.json({ limit: '10mb' }));

app.post('/precommit', async (req, res) => {
  const message = req?.body?.message ?? '';
  if (!message || typeof message !== 'string' || !message.trim()) {
    return res.status(400).send({ error: 'missing message' });
  }
  try {
    runGit(['add', '-A']);
    const status = runGit(['status', '--porcelain']);
    if (status.trim()) {
      runGit(['commit', '-m', message.trim()]);
      return res.send({ ok: true, committed: true });
    }
    return res.send({ ok: true, committed: false });
  } catch (err) {
    return res.status(500).send({ error: err?.message ?? 'git execution error' });
  }
});

app.post('/apply', async (req, res) => {
  const filePath = req?.body?.filePath ?? '';
  const content = req?.body?.content;
  if (!filePath || typeof content !== 'string') {
    return res.status(400).send({ error: 'invalid payload' });
  }
  const safeFullPath = resolveSafeRepoPath(filePath);
  if (!safeFullPath) {
    return res.status(403).send({ error: 'path traversal denied' });
  }
  try {
    await fs.promises.mkdir(path.dirname(safeFullPath), { recursive: true });
    await fs.promises.writeFile(safeFullPath, content, 'utf8');
    return res.send({ ok: true, path: safeFullPath });
  } catch (err) {
    return res.status(500).send({ error: err?.message ?? 'file write error' });
  }
});

if (require.main === module) {
  const port = resolvePort();
  app.listen(port, () => {
    process.stdout.write(`MCP HTTP bridge listening on port ${port}\n`);
  });
}

module.exports = { app, resolvePort, resolveSafeRepoPath, runGit };
