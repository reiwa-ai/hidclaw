"""WebUI HTML templates."""

HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pico HID Bridge</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #101214;
      --surface: #191d20;
      --surface-2: #20262a;
      --line: #313a40;
      --text: #f4f5f2;
      --muted: #aab3ad;
      --accent: #56b38f;
      --warn: #d8a94e;
      --danger: #df5b57;
      --ok: #61c49b;
      --focus: #89c2ff;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-width: 320px;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }

    button, input, textarea {
      font: inherit;
    }

    button {
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface-2);
      color: var(--text);
      padding: 0 14px;
      cursor: pointer;
    }

    [hidden] {
      display: none !important;
    }

    button:hover { border-color: var(--muted); }
    button:focus-visible, textarea:focus-visible, input:focus-visible {
      outline: 2px solid var(--focus);
      outline-offset: 2px;
    }

    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #07110d;
      font-weight: 700;
    }

    button.danger {
      background: var(--danger);
      border-color: var(--danger);
      color: #160706;
      font-weight: 800;
    }

    button:disabled {
      cursor: not-allowed;
      opacity: .55;
    }

    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
      background: #15181a;
    }

    h1 {
      margin: 0;
      font-size: 18px;
      line-height: 1.2;
      font-weight: 800;
    }

    .badges {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
    }

    .view-nav {
      display: flex;
      gap: 8px;
      margin-left: auto;
    }

    .nav-button {
      min-height: 34px;
      background: transparent;
      color: var(--muted);
      border-color: var(--line);
      font-weight: 800;
    }

    .nav-button[aria-current="page"] {
      background: #283139;
      border-color: var(--focus);
      color: var(--text);
      box-shadow: inset 0 -2px 0 var(--focus);
    }

    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 4px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--surface);
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }

    .badge.ok { color: var(--ok); border-color: rgba(97, 196, 155, .55); }
    .badge.warn { color: var(--warn); border-color: rgba(216, 169, 78, .55); }
    .badge.danger { color: #ffb7b4; border-color: rgba(223, 91, 87, .65); }

    main {
      display: grid;
      grid-template-columns: minmax(0, 1.55fr) minmax(360px, .95fr);
      gap: 16px;
      padding: 16px;
    }

    .view[hidden] {
      display: none;
    }

    .logs-main {
      grid-template-columns: 1fr;
    }

    .panel {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      overflow: hidden;
    }

    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 52px;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      background: #171b1e;
    }

    .panel-title {
      margin: 0;
      font-size: 14px;
      line-height: 1.2;
      font-weight: 800;
      color: var(--muted);
      text-transform: uppercase;
    }

    .screen-panel {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
    }

    .screen-wrap {
      display: grid;
      place-items: center;
      width: 100%;
      height: 100%;
      min-height: 320px;
      background: #0b0d0e;
      overflow: hidden;
    }

    .screen-wrap img {
      width: auto;
      height: auto;
      max-width: none;
      max-height: none;
      display: block;
    }

    .stack {
      display: grid;
      gap: 16px;
    }

    .form {
      display: grid;
      gap: 12px;
      padding: 12px;
    }

    .tabs {
      display: flex;
      gap: 8px;
      padding: 12px 12px 0;
    }

    .tab-button {
      min-height: 34px;
      background: #14181b;
      color: var(--muted);
      border-color: var(--line);
      font-weight: 700;
    }

    .tab-button:hover {
      color: var(--text);
      border-color: #56636b;
    }

    .tab-button[aria-selected="true"] {
      background: #283139;
      border-color: var(--focus);
      color: var(--text);
      font-weight: 800;
      box-shadow: inset 0 -2px 0 var(--focus);
    }

    .tab-panel[hidden] {
      display: none;
    }

    textarea {
      width: 100%;
      min-height: 112px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #111416;
      color: var(--text);
      padding: 10px;
    }

    .row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }

    .message {
      min-height: 22px;
      color: var(--muted);
      font-size: 14px;
    }

    .message.error { color: #ffb7b4; }
    .message.ok { color: var(--ok); }
    .message.warn { color: var(--warn); }

    .log-list {
      display: grid;
      max-height: 344px;
      overflow: auto;
    }

    .log-list.short {
      max-height: 240px;
    }

    .log-row {
      display: grid;
      grid-template-columns: 136px 1fr;
      gap: 10px;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      font-size: 13px;
    }

    .log-row:last-child { border-bottom: 0; }
    .log-time { color: var(--muted); white-space: nowrap; }
    .log-main { min-width: 0; overflow-wrap: anywhere; }
    .log-sub { color: var(--muted); margin-top: 4px; }

    .log-toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
    }

    .log-toolbar label {
      display: inline-grid;
      gap: 4px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }

    .token-summary {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-left: auto;
      align-items: center;
    }

    .token-summary-item {
      display: grid;
      gap: 2px;
      min-width: 118px;
      padding: 7px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #111416;
    }

    .token-summary-label {
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
    }

    .token-summary-value {
      color: var(--text);
      font-size: 18px;
      font-weight: 900;
      font-variant-numeric: tabular-nums;
      line-height: 1;
    }

    input[type="datetime-local"] {
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #111416;
      color: var(--text);
      padding: 0 10px;
    }

    .log-overview {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }

    .detail-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(260px, .85fr);
      min-height: 420px;
    }

    .timeline-list, .token-list {
      max-height: 58vh;
      min-height: 360px;
      overflow: auto;
    }

    .timeline-list {
      border-right: 1px solid var(--line);
    }

    .timeline-row, .token-row {
      height: 48px;
      padding: 9px 12px;
      border-bottom: 1px solid var(--line);
      font-size: 13px;
      overflow: hidden;
    }

    .timeline-row {
      display: grid;
      grid-template-columns: 92px 92px 1fr;
      gap: 10px;
      align-items: center;
    }

    .timeline-kind {
      color: var(--warn);
      font-weight: 800;
      text-transform: uppercase;
    }

    .timeline-main {
      min-width: 0;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }

    .timeline-main > div:first-child,
    .timeline-main .log-sub {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .timeline-main .log-sub {
      margin-top: 2px;
    }

    .token-row {
      display: grid;
      grid-template-columns: 92px 1fr 72px;
      gap: 10px;
      align-items: center;
    }

    .token-track {
      height: 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #111416;
      overflow: hidden;
    }

    .token-bar {
      height: 100%;
      width: 0%;
      background: var(--accent);
    }

    .token-value {
      color: var(--muted);
      text-align: right;
      font-variant-numeric: tabular-nums;
    }

    .kv {
      display: grid;
      grid-template-columns: 132px 1fr;
      gap: 8px 12px;
      padding: 12px;
      font-size: 14px;
    }

    .activity {
      display: grid;
      gap: 6px;
      margin: 12px 12px 0;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #111416;
    }

    .activity-title {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }

    .activity-main {
      color: var(--text);
      font-size: 16px;
      font-weight: 800;
      overflow-wrap: anywhere;
    }

    .activity-detail {
      min-height: 18px;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }

    .kv div:nth-child(odd) { color: var(--muted); }
    .kv div:nth-child(even) { overflow-wrap: anywhere; }

    @media (max-width: 980px) {
      header {
        align-items: flex-start;
        flex-direction: column;
      }

      .view-nav {
        margin-left: 0;
      }

      .badges {
        justify-content: flex-start;
      }

      main, .log-overview, .detail-grid {
        grid-template-columns: 1fr;
      }

      .token-summary {
        width: 100%;
        margin-left: 0;
      }

      .token-summary-item {
        flex: 1 1 140px;
      }

      .timeline-list {
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
    }

    @media (max-width: 520px) {
      header, main {
        padding-left: 10px;
        padding-right: 10px;
      }

      .panel-head, .row {
        align-items: stretch;
      }

      .panel-head, .row {
        flex-direction: column;
      }

      button {
        width: 100%;
      }

      .log-row, .kv {
        grid-template-columns: 1fr;
      }

      .timeline-row, .token-row {
        grid-template-columns: 1fr;
        height: auto;
        min-height: 48px;
      }

      .screen-wrap {
        height: min(58vh, 420px);
        min-height: 240px;
      }
    }
  </style>
</head>
<body>
  <header>
    <h1>Pico HID Bridge</h1>
    <nav class="view-nav" aria-label="Main views">
      <button id="operationViewButton" class="nav-button" type="button" aria-current="page">Operation</button>
      <button id="logsViewButton" class="nav-button" type="button">Logs</button>
    </nav>
    <div class="badges">
      <span id="stateBadge" class="badge">starting</span>
      <span id="stopBadge" class="badge">stop clear</span>
      <span id="planningBadge" class="badge">planning off</span>
    </div>
  </header>

  <main id="operationView" class="view operation-view">
    <section class="panel screen-panel">
      <div class="panel-head">
        <h2 class="panel-title">Screen</h2>
        <div class="row">
          <button id="refreshScreen" type="button">Refresh</button>
        </div>
      </div>
      <div class="screen-wrap">
        <img id="screen" alt="capture" src="/api/screenshot">
      </div>
    </section>

    <div class="stack">
      <section class="panel">
        <div class="panel-head">
          <h2 class="panel-title">Command</h2>
        </div>
        <div class="tabs" role="tablist" aria-label="Command mode">
          <button id="requestTab" class="tab-button" type="button" role="tab" aria-selected="true" aria-controls="requestPanel" data-tab="request">Request</button>
          <button id="planTab" class="tab-button" type="button" role="tab" aria-selected="false" aria-controls="requestPanel" data-tab="plan">Plan</button>
          <button id="manualTab" class="tab-button" type="button" role="tab" aria-selected="false" aria-controls="manualPanel" data-tab="manual">Manual HID</button>
        </div>
        <form id="commandForm" class="form">
          <div id="requestPanel" class="tab-panel" role="tabpanel" aria-labelledby="requestTab">
            <textarea id="command" name="command" spellcheck="false" autocomplete="off">open browser</textarea>
            <div class="row">
              <button id="sendButton" class="primary" type="submit">Send</button>
              <button id="suspendButton" type="button">Suspend</button>
              <button id="resumeButton" type="button">Resume</button>
              <button id="stopButton" class="danger" type="button">Emergency Stop</button>
            </div>
            <div id="approvalNotice" class="message warn" hidden></div>
            <div id="approvalControls" class="row" hidden>
              <button id="approveButton" class="primary" type="button" disabled>Approve Plan</button>
              <button id="rejectButton" type="button" disabled>Reject Plan</button>
            </div>
          </div>
          <div id="manualPanel" class="tab-panel" role="tabpanel" aria-labelledby="manualTab" hidden>
            <textarea id="manualCommand" name="manualCommand" spellcheck="false" autocomplete="off">PING</textarea>
            <div class="row">
              <button id="manualSendButton" type="button">Send Manual HID</button>
            </div>
          </div>
          <div id="message" class="message"></div>
        </form>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2 class="panel-title">Status</h2>
        </div>
        <div id="activityStatus" class="activity">
          <div class="activity-title">Current Status</div>
          <div id="activityMain" class="activity-main">Ready</div>
          <div id="activityDetail" class="activity-detail"></div>
        </div>
        <div id="statusGrid" class="kv"></div>
      </section>
    </div>
  </main>

  <main id="logsView" class="view logs-main" hidden>
    <section class="log-toolbar">
      <button id="refreshLogs" type="button">Refresh</button>
      <label>
        From
        <input id="logFrom" type="datetime-local">
      </label>
      <label>
        To
        <input id="logTo" type="datetime-local">
      </label>
      <button id="searchLogs" type="button">Search Date/Time</button>
      <div id="tokenSummary" class="token-summary" aria-live="polite">
        <div class="token-summary-item">
          <div class="token-summary-label">Total Tokens</div>
          <div id="tokenTotalAll" class="token-summary-value">0</div>
        </div>
        <div class="token-summary-item">
          <div class="token-summary-label">This Month</div>
          <div id="tokenTotalMonth" class="token-summary-value">0</div>
        </div>
        <div id="tokenRangeSummary" class="token-summary-item" hidden>
          <div class="token-summary-label">Filtered</div>
          <div id="tokenTotalRange" class="token-summary-value">0</div>
        </div>
      </div>
    </section>

    <section class="log-overview">
      <section class="panel">
        <div class="panel-head">
          <h2 class="panel-title">User Log</h2>
        </div>
        <div id="userLog" class="log-list short"></div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2 class="panel-title">Operation Log</h2>
        </div>
        <div id="operationLog" class="log-list short"></div>
      </section>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2 class="panel-title">System Log</h2>
        <h2 class="panel-title">Token Graph</h2>
      </div>
      <div class="detail-grid">
        <div id="detailLog" class="timeline-list"></div>
        <div id="tokenGraph" class="token-list"></div>
      </div>
    </section>
  </main>

  <script>
    const screenEl = document.getElementById("screen");
    const screenWrap = document.querySelector(".screen-wrap");
    const operationView = document.getElementById("operationView");
    const logsView = document.getElementById("logsView");
    const operationViewButton = document.getElementById("operationViewButton");
    const logsViewButton = document.getElementById("logsViewButton");
    const commandEl = document.getElementById("command");
    const manualCommandEl = document.getElementById("manualCommand");
    const messageEl = document.getElementById("message");
    const stateBadge = document.getElementById("stateBadge");
    const stopBadge = document.getElementById("stopBadge");
    const planningBadge = document.getElementById("planningBadge");
    const sendButton = document.getElementById("sendButton");
    const stopButton = document.getElementById("stopButton");
    const suspendButton = document.getElementById("suspendButton");
    const resumeButton = document.getElementById("resumeButton");
    const approvalNotice = document.getElementById("approvalNotice");
    const approvalControls = document.getElementById("approvalControls");
    const approveButton = document.getElementById("approveButton");
    const rejectButton = document.getElementById("rejectButton");
    const manualSendButton = document.getElementById("manualSendButton");
    const activityMain = document.getElementById("activityMain");
    const activityDetail = document.getElementById("activityDetail");
    const statusGrid = document.getElementById("statusGrid");
    const userLog = document.getElementById("userLog");
    const operationLog = document.getElementById("operationLog");
    const detailLog = document.getElementById("detailLog");
    const tokenGraph = document.getElementById("tokenGraph");
    const refreshLogsButton = document.getElementById("refreshLogs");
    const searchLogsButton = document.getElementById("searchLogs");
    const logFromEl = document.getElementById("logFrom");
    const logToEl = document.getElementById("logTo");
    const tokenTotalAll = document.getElementById("tokenTotalAll");
    const tokenTotalMonth = document.getElementById("tokenTotalMonth");
    const tokenRangeSummary = document.getElementById("tokenRangeSummary");
    const tokenTotalRange = document.getElementById("tokenTotalRange");
    const COMMAND_POLL_MS = 1000;
    const SCREEN_POLL_MS = 2500;
    let requestBusy = false;
    let manualBusy = false;
    let busyScreenRefreshTimer = null;
    let activeCommandMode = "request";
    let screenFitFrame = 0;

    function setMessage(text, kind = "") {
      messageEl.textContent = text || "";
      messageEl.className = "message" + (kind ? " " + kind : "");
    }

    function classifyBadge(el, text, kind) {
      el.textContent = text;
      el.className = "badge" + (kind ? " " + kind : "");
    }

    function fmtTime(value) {
      if (!value) return "";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return date.toLocaleTimeString();
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));
    }

    function fitScreenImageToFrame() {
      screenFitFrame = 0;
      if (!screenWrap) return;
      const bounds = screenWrap.getBoundingClientRect();
      const frameWidth = Math.floor(bounds.width);
      const frameHeight = Math.floor(bounds.height);
      if (frameWidth <= 0 || frameHeight <= 0) return;

      const naturalWidth = screenEl.naturalWidth || 16;
      const naturalHeight = screenEl.naturalHeight || 9;
      const aspect = naturalWidth / naturalHeight;
      let width = frameWidth;
      let height = Math.round(width / aspect);
      if (height > frameHeight) {
        height = frameHeight;
        width = Math.round(height * aspect);
      }

      screenEl.style.width = `${Math.max(1, width)}px`;
      screenEl.style.height = `${Math.max(1, height)}px`;
    }

    function fitScreenImageBeforeRefresh() {
      if (screenFitFrame) {
        window.cancelAnimationFrame(screenFitFrame);
        screenFitFrame = 0;
      }
      fitScreenImageToFrame();
    }

    function scheduleScreenFit() {
      if (screenFitFrame) {
        window.cancelAnimationFrame(screenFitFrame);
      }
      screenFitFrame = window.requestAnimationFrame(fitScreenImageToFrame);
    }

    function renderLogs(el, rows, emptyText) {
      el.textContent = "";
      if (!rows || rows.length === 0) {
        const empty = document.createElement("div");
        empty.className = "log-row";
        empty.innerHTML = `<div class="log-time"></div><div class="log-main">${emptyText}</div>`;
        el.appendChild(empty);
        return;
      }

      rows.slice().reverse().forEach((row) => {
        const item = document.createElement("div");
        item.className = "log-row";
        const summary = row.command || row.input || row.event || row.result || row.message || row.status || "";
        const detail = row.error || row.reason || row.normalized || row.source || "";
        item.innerHTML = `
          <div class="log-time">${fmtTime(row.created_at)}</div>
          <div class="log-main">
            <div>${escapeHtml(summary)}</div>
            ${detail ? `<div class="log-sub">${escapeHtml(detail)}</div>` : ""}
          </div>
        `;
        el.appendChild(item);
      });
    }

    function buildTimeline(data) {
      const rows = [];
      (data.user_logs || []).forEach((row) => rows.push({
        created_at: row.created_at,
        kind: "user",
        text: `User Input '${row.input || ""}'`,
        detail: row.planning ? "planning" : row.source || "",
        tokens: 0,
      }));
      (data.operation_logs || []).forEach((row) => rows.push({
        created_at: row.created_at,
        kind: row.action_type === "KEY" || row.action_type === "TEXT" || String(row.command || "").startsWith("KEY ") ? "hid" : "operation",
        text: row.normalized || row.command || row.message || "",
        detail: row.status || row.error || row.source || "",
        tokens: 0,
      }));
      (data.system_logs || []).forEach((row) => rows.push({
        created_at: row.created_at,
        kind: "system",
        text: row.message || row.event || "",
        detail: row.status || "",
        tokens: 0,
      }));
      (data.screenshot_logs || []).forEach((row) => rows.push({
        created_at: row.created_at,
        kind: "screen",
        text: `Screencapture ${row.event || ""}`.trim(),
        detail: row.width && row.height ? `${row.width}x${row.height}` : row.path || "",
        tokens: 0,
      }));
      (data.error_logs || []).forEach((row) => rows.push({
        created_at: row.created_at,
        kind: "error",
        text: row.message || "",
        detail: row.domain || "",
        tokens: 0,
      }));
      return rows.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
    }

    function renderTimeline(rows) {
      detailLog.textContent = "";
      if (!rows.length) {
        detailLog.innerHTML = '<div class="timeline-row"><div></div><div></div><div class="timeline-main">No logs</div></div>';
        return;
      }
      rows.forEach((row) => {
        const item = document.createElement("div");
        item.className = "timeline-row";
        item.innerHTML = `
          <div class="log-time">${escapeHtml(fmtTime(row.created_at))}</div>
          <div class="timeline-kind">${escapeHtml(row.kind)}</div>
          <div class="timeline-main">
            <div>${escapeHtml(row.text)}</div>
            ${row.detail ? `<div class="log-sub">${escapeHtml(row.detail)}</div>` : ""}
          </div>
        `;
        detailLog.appendChild(item);
      });
    }

    function tokenTotal(row) {
      return Number(row.total_tokens || row.estimated_tokens || row.input_tokens || row.output_tokens || 0);
    }

    function totalFromSummary(summary) {
      return Math.max(
        Number(summary.total_tokens || 0),
        Number(summary.estimated_tokens || 0),
        Number(summary.input_tokens || 0) + Number(summary.output_tokens || 0)
      );
    }

    function formatTokenCount(value) {
      return new Intl.NumberFormat().format(Number(value || 0));
    }

    function monthTokenParams() {
      const now = new Date();
      const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
      const nextMonthStart = new Date(now.getFullYear(), now.getMonth() + 1, 1);
      const params = new URLSearchParams();
      params.set("from", monthStart.toISOString());
      params.set("to", nextMonthStart.toISOString());
      return params;
    }

    async function refreshTokenSummary(from, to) {
      const monthParams = monthTokenParams();
      const requests = [
        api("/api/tokens"),
        api("/api/tokens?" + monthParams.toString()),
      ];
      const rangeParams = new URLSearchParams();
      if (from) rangeParams.set("from", from);
      if (to) rangeParams.set("to", to);
      const hasRange = rangeParams.has("from") || rangeParams.has("to");
      if (hasRange) {
        requests.push(api("/api/tokens?" + rangeParams.toString()));
      }
      const [allTokens, monthTokens, rangeTokens] = await Promise.all(requests);
      tokenTotalAll.textContent = formatTokenCount(totalFromSummary(allTokens));
      tokenTotalMonth.textContent = formatTokenCount(totalFromSummary(monthTokens));
      tokenRangeSummary.hidden = !hasRange;
      if (hasRange) {
        tokenTotalRange.textContent = formatTokenCount(totalFromSummary(rangeTokens));
      }
    }

    function bucketTokenUsage(timelineRows, tokenRows) {
      const sortedTokens = (tokenRows || []).slice().sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
      return timelineRows.map((row, index) => {
        const currentTime = Date.parse(row.created_at);
        const previousTime = index < timelineRows.length - 1 ? Date.parse(timelineRows[index + 1].created_at) : Number.NEGATIVE_INFINITY;
        const tokens = sortedTokens
          .filter((token) => {
            const tokenTime = Date.parse(token.created_at);
            return tokenTime > previousTime && tokenTime <= currentTime;
          })
          .reduce((total, token) => total + tokenTotal(token), 0);
        return { ...row, tokens };
      });
    }

    function renderTokenGraph(rows) {
      tokenGraph.textContent = "";
      const maxTokens = Math.max(1, ...rows.map((row) => Number(row.tokens || 0)));
      rows.forEach((row) => {
        const tokens = Number(row.tokens || 0);
        const item = document.createElement("div");
        item.className = "token-row";
        item.innerHTML = `
          <div class="log-time">${escapeHtml(fmtTime(row.created_at))}</div>
          <div class="token-track"><div class="token-bar" style="width: ${(tokens / maxTokens) * 100}%"></div></div>
          <div class="token-value">${tokens}</div>
        `;
        tokenGraph.appendChild(item);
      });
    }

    function toIsoFromLocalInput(value) {
      if (!value) return "";
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? "" : date.toISOString();
    }

    async function refreshDetailLogs() {
      const params = new URLSearchParams();
      const from = toIsoFromLocalInput(logFromEl.value);
      const to = toIsoFromLocalInput(logToEl.value);
      if (from) params.set("from", from);
      if (to) params.set("to", to);
      params.set("limit", "500");
      const data = await api("/api/logs/detail?" + params.toString());
      renderLogs(userLog, data.user_logs || [], "No user input");
      renderLogs(operationLog, data.operation_logs || [], "No operations");
      const timeline = buildTimeline(data);
      renderTimeline(timeline);
      renderTokenGraph(bucketTokenUsage(timeline, data.token_usage || []));
      await refreshTokenSummary(from, to);
    }

    function renderStatus(status) {
      const busy = requestBusy || manualBusy || !!status.command_running;
      const approvalPending = !!status.approval_pending;
      const longOperation = status.long_operation || {};
      const tokenPrediction = status.token_prediction || {};
      const running = status.emergency_stopped ? "stopped" : (approvalPending ? "approval pending" : (busy ? "running" : (status.suspended ? "suspended" : "ready")));
      classifyBadge(stateBadge, running, status.emergency_stopped ? "danger" : (approvalPending || busy || status.suspended ? "warn" : "ok"));
      classifyBadge(stopBadge, status.emergency_stopped ? "emergency stop" : "stop clear", status.emergency_stopped ? "danger" : "ok");
      classifyBadge(planningBadge, activeCommandMode === "plan" ? "plan mode" : "request mode", activeCommandMode === "plan" ? "warn" : "");
      activityMain.textContent = status.current_status || "Ready";
      activityDetail.textContent = status.current_detail || "";
      sendButton.disabled = busy || approvalPending || !!status.suspended || !!status.emergency_stopped;
      manualSendButton.disabled = busy || approvalPending || !!status.suspended || !!status.emergency_stopped;
      stopButton.disabled = !(busy || approvalPending);
      suspendButton.disabled = approvalPending || !!status.emergency_stopped || !!status.suspended;
      resumeButton.disabled = approvalPending || !!status.emergency_stopped || !status.suspended;
      approveButton.disabled = busy || !approvalPending || !!status.emergency_stopped;
      rejectButton.disabled = busy || !approvalPending || !!status.emergency_stopped;
      approvalControls.hidden = !approvalPending;
      approvalNotice.hidden = !approvalPending;
      approvalNotice.textContent = approvalPending
        ? (status.approval_detail || "This plan requires approval before it can continue.")
        : "";

      const pairs = [
        ["Phase", status.current_phase || "idle"],
        ["Host", status.bind_host + ":" + status.bind_port],
        ["HID", status.hid_port],
        ["Capture", status.capture_device],
        ["Approval", status.approval_status || "idle"],
        ["Approval command", status.approval_command || ""],
        ["Progress", longOperation.total_steps ? `${longOperation.completed_steps || 0}/${longOperation.total_steps} (${longOperation.estimated_percent || 0}%)` : ""],
        ["Current step", longOperation.current_step || ""],
        ["Long warning", longOperation.warning ? "active" : ""],
        ["Token prediction", tokenPrediction.estimated_tokens ? `${formatTokenCount(tokenPrediction.estimated_tokens)} tokens` : ""],
        ["Token budget", tokenPrediction.message || ""],
        ["Last command", status.last_command || ""],
        ["Last error", status.last_error || ""],
        ["Started", fmtTime(status.started_at)],
      ];
      statusGrid.textContent = "";
      pairs.forEach(([key, value]) => {
        const k = document.createElement("div");
        const v = document.createElement("div");
        k.textContent = key;
        v.textContent = value;
        statusGrid.appendChild(k);
        statusGrid.appendChild(v);
      });
      scheduleScreenFit();

    }

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.error || body.message || response.statusText);
      }
      return body;
    }

    async function refreshStatus() {
      try {
        const status = await api("/api/status");
        renderStatus(status);
        return status;
      } catch (error) {
        setMessage(error.message, "error");
        return null;
      }
    }

    function refreshScreen() {
      fitScreenImageBeforeRefresh();
      screenEl.src = "/api/screenshot?ts=" + Date.now();
    }

    function startBusyScreenRefresh() {
      if (busyScreenRefreshTimer !== null) return;
      refreshScreen();
      busyScreenRefreshTimer = window.setInterval(refreshScreen, SCREEN_POLL_MS);
    }

    function stopBusyScreenRefresh() {
      if (busyScreenRefreshTimer === null) return;
      window.clearInterval(busyScreenRefreshTimer);
      busyScreenRefreshTimer = null;
    }

    async function pollOperationUntilIdle(kind) {
      let sawServerRunning = false;
      while ((kind === "request" && requestBusy) || (kind === "manual" && manualBusy)) {
        await new Promise((resolve) => window.setTimeout(resolve, COMMAND_POLL_MS));
        const status = await refreshStatus();
        refreshScreen();
        if (!status) continue;

        if (status.command_running) {
          sawServerRunning = true;
          continue;
        }

        if (sawServerRunning || status.current_phase === "idle" || status.current_phase === "error") {
          if (kind === "request") requestBusy = false;
          if (kind === "manual") manualBusy = false;
          stopBusyScreenRefresh();
          renderStatus(status);
          refreshScreen();
          return status;
        }
      }
      stopBusyScreenRefresh();
    }

    function watchOperation(operationPromise, kind) {
      startBusyScreenRefresh();
      pollOperationUntilIdle(kind);
      operationPromise
        .then((result) => {
          setMessage(result.message || "sent", "ok");
        })
        .catch((error) => {
          setMessage(error.message, "error");
        })
        .finally(async () => {
          if (kind === "request") requestBusy = false;
          if (kind === "manual") manualBusy = false;
          stopBusyScreenRefresh();
          await refreshStatus();
          refreshScreen();
          if (!logsView.hidden) {
            await refreshDetailLogs();
          }
        });
    }

    function showView(name) {
      const showLogs = name === "logs";
      operationView.hidden = showLogs;
      logsView.hidden = !showLogs;
      operationViewButton.setAttribute("aria-current", showLogs ? "false" : "page");
      logsViewButton.setAttribute("aria-current", showLogs ? "page" : "false");
      if (showLogs) {
        refreshDetailLogs().catch((error) => setMessage(error.message, "error"));
      } else {
        scheduleScreenFit();
      }
    }

    operationViewButton.addEventListener("click", () => showView("operation"));
    logsViewButton.addEventListener("click", () => showView("logs"));
    document.getElementById("refreshScreen").addEventListener("click", refreshScreen);
    refreshLogsButton.addEventListener("click", () => refreshDetailLogs().catch((error) => setMessage(error.message, "error")));
    searchLogsButton.addEventListener("click", () => refreshDetailLogs().catch((error) => setMessage(error.message, "error")));
    detailLog.addEventListener("scroll", () => {
      tokenGraph.scrollTop = detailLog.scrollTop;
    });
    tokenGraph.addEventListener("scroll", () => {
      detailLog.scrollTop = tokenGraph.scrollTop;
    });

    document.querySelectorAll(".tab-button").forEach((button) => {
      button.addEventListener("click", () => {
        const selected = button.dataset.tab;
        activeCommandMode = selected || "request";
        document.querySelectorAll(".tab-button").forEach((candidate) => {
          candidate.setAttribute("aria-selected", candidate.dataset.tab === selected ? "true" : "false");
        });
        document.getElementById("requestPanel").hidden = selected === "manual";
        document.getElementById("manualPanel").hidden = selected !== "manual";
        refreshStatus();
      });
    });

    document.getElementById("commandForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setMessage("");
      requestBusy = true;
      sendButton.disabled = true;
      manualSendButton.disabled = true;
      stopButton.disabled = false;
      activityMain.textContent = "Computer Use API calling";
      activityDetail.textContent = commandEl.value.trim();
      const operationPromise = api("/api/command", {
          method: "POST",
          body: JSON.stringify({
            command: commandEl.value,
            planning: activeCommandMode === "plan",
          }),
      });
      watchOperation(operationPromise, "request");
    });

    manualSendButton.addEventListener("click", async () => {
      setMessage("");
      manualBusy = true;
      sendButton.disabled = true;
      manualSendButton.disabled = true;
      stopButton.disabled = false;
      activityMain.textContent = "Manual HID sending";
      activityDetail.textContent = manualCommandEl.value.trim();
      const operationPromise = api("/api/manual-hid", {
          method: "POST",
          body: JSON.stringify({ command: manualCommandEl.value }),
      });
      watchOperation(operationPromise, "manual");
    });

    stopButton.addEventListener("click", async () => {
      try {
        const result = await api("/api/emergency-stop", { method: "POST", body: "{}" });
        setMessage(result.message || "stopped", "ok");
        await refreshStatus();
      } catch (error) {
        setMessage(error.message, "error");
      }
    });

    suspendButton.addEventListener("click", async () => {
      try {
        await api("/api/suspend", { method: "POST", body: "{}" });
        await refreshStatus();
      } catch (error) {
        setMessage(error.message, "error");
      }
    });

    resumeButton.addEventListener("click", async () => {
      try {
        await api("/api/resume", { method: "POST", body: "{}" });
        await refreshStatus();
      } catch (error) {
        setMessage(error.message, "error");
      }
    });

    approveButton.addEventListener("click", async () => {
      setMessage("");
      requestBusy = true;
      sendButton.disabled = true;
      manualSendButton.disabled = true;
      approveButton.disabled = true;
      rejectButton.disabled = true;
      stopButton.disabled = false;
      activityMain.textContent = "Approval accepted";
      activityDetail.textContent = "Executing approved plan";
      const operationPromise = api("/api/approve", { method: "POST", body: "{}" });
      watchOperation(operationPromise, "request");
    });

    rejectButton.addEventListener("click", async () => {
      try {
        const result = await api("/api/reject", { method: "POST", body: "{}" });
        setMessage(result.message || "rejected", "ok");
        await refreshStatus();
        refreshScreen();
        if (!logsView.hidden) {
          await refreshDetailLogs();
        }
      } catch (error) {
        setMessage(error.message, "error");
      }
    });

    screenEl.addEventListener("load", scheduleScreenFit);
    screenEl.addEventListener("error", () => setMessage("capture unavailable", "error"));
    window.addEventListener("resize", scheduleScreenFit);
    if (window.ResizeObserver && screenWrap) {
      new ResizeObserver(scheduleScreenFit).observe(screenWrap);
    }

    refreshStatus();
    scheduleScreenFit();
    setInterval(refreshStatus, 1000);
  </script>
</body>
</html>
"""
