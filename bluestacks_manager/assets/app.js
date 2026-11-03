const state = {
  token: localStorage.getItem('manager_token') || '',
  configPath: localStorage.getItem('manager_config_path') || '',
  installations: [],
  instances: [],
  presets: [],
  profileCodes: [],
  backups: [],
  preflight: null,
  platform: null,
  history: [],
  selected: new Set(),
};

const $ = (id) => document.getElementById(id);
const apiBase = location.origin;

function icon(name, cls = '') {
  return `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true"><use href="icons.svg#${name}"></use></svg>`;
}

function toast(message, type = 'ok') {
  const el = $('toast');
  el.className = `toast ${type}`;
  el.textContent = message;
  el.classList.remove('hidden');
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.add('hidden'), 3200);
}

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (state.token) headers['X-Manager-Token'] = state.token;
  const response = await fetch(apiBase + path, { ...options, headers });
  let data = {};
  try { data = await response.json(); } catch {}
  if (!response.ok || data.ok === false) {
    const error = new Error(data.error || `请求失败 (${response.status})`);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data.data !== undefined ? data.data : data;
}

async function loadIcons() {
  try {
    const response = await fetch('icons.svg');
    const svg = await response.text();
    $('icons').innerHTML = svg;
  } catch {}
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('manager_theme', theme);
  const use = $('btn-theme').querySelector('use');
  use.setAttribute('href', theme === 'dark' ? 'icons.svg#i-sun' : 'icons.svg#i-moon');
}

async function bootstrapTheme() {
  const saved = localStorage.getItem('manager_theme');
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  setTheme(saved || (prefersDark ? 'dark' : 'light'));
}

async function bootstrapToken() {
  if (window.pywebview && window.pywebview.api) {
    try {
      const token = await window.pywebview.api.get_token();
      if (token) {
        state.token = token;
        localStorage.setItem('manager_token', token);
      }
    } catch {}
  }
}

function renderNav() {
  $('nav-version').textContent = `v${state.platform?.version || '1.0.0'}`;
  const running = state.platform?.bluestacks_processes?.length || 0;
  const ok = state.platform && state.instances.length >= 0;
  const pill = $('nav-status');
  pill.classList.toggle('ok', ok);
  pill.querySelector('span:last-child').textContent = running ? `运行中 ${running}` : '本地就绪';
}

function renderTopbar() {
  const configPath = state.configPath || (state.installations[0] && state.installations[0].config_path) || '';
  $('config-path').value = configPath;
  const path = $('settings-config-path');
  if (path) path.value = configPath;
  const devicePath = $('device-config-path');
  if (devicePath) devicePath.value = configPath;
}

function renderInstallation() {
  const installation = state.installations[0] || {};
  const rows = [
    ['安装源', installation.source || '未检测到'],
    ['配置文件', installation.config_path || '未找到'],
    ['数据目录', installation.data_path || '未找到'],
    ['程序目录', installation.install_path || '未找到'],
    ['版本', installation.version || '未知'],
    ['实例数量', String(installation.instance_count ?? state.instances.length)],
  ];
  $('installation-detail').innerHTML = rows.map(([key, value]) => `<div class="detail-row"><span class="key">${key}</span><span class="value">${value || '—'}</span></div>`).join('');
  const badge = $('installation-badge');
  if (state.installations.length === 0) {
    badge.className = 'badge red';
    badge.textContent = '未检测到';
  } else {
    badge.className = 'badge green';
    badge.textContent = '已检测到';
  }
}

function renderDashboard() {
  const count = state.instances.length;
  const rootCount = state.instances.filter((i) => i.root_enabled).length;
  const running = state.platform?.bluestacks_processes?.length || 0;
  $('stat-instances').textContent = count;
  $('stat-instances-sub').textContent = count ? `${state.installations[0]?.config_path || ''}` : '等待检测';
  $('stat-root').textContent = rootCount;
  $('stat-root-sub').textContent = rootCount ? `${rootCount}/${count} 已配置 Root` : '未启用';
  $('stat-running').textContent = running;
  $('stat-running-sub').textContent = running ? state.platform.bluestacks_processes.join(', ') : '未检测到进程';
  $('stat-backups').textContent = state.backups.length;
  $('stat-backups-sub').textContent = state.backups.length ? `最近 ${state.backups[0]?.backup_id || ''}` : '未创建备份';
  renderInstallation();
}

function selectedIds() {
  return state.instances.map((item) => item.instance_id).filter((id) => state.selected.has(id));
}

function renderSelectedCount() {
  const ids = selectedIds();
  $('selected-count').textContent = `已选择 ${ids.length} 个实例`;
  $('check-all').checked = state.instances.length > 0 && state.selected.size === state.instances.length;
}

function instanceCard(item) {
  const selected = state.selected.has(item.instance_id);
  const device = item.device || {};
  const deviceText = [device.manufacturer, device.brand, device.model].filter(Boolean).join(' ') || device.profile_code || '默认机型';
  const warnings = item.warnings || [];
  return `
    <article class="card instance-card ${selected ? 'selected' : ''}">
      <div class="instance-top">
        <label class="check-all">
          <input type="checkbox" data-instance="${item.instance_id}" ${selected ? 'checked' : ''} />
          <span><span class="instance-name">${item.display_name || item.instance_id}</span><span class="instance-id">${item.instance_id}</span></span>
        </label>
        <span class="badge ${item.root_enabled ? 'green' : 'neutral'}">${item.root_enabled ? 'Root 已配置' : 'Root 未启用'}</span>
      </div>
      <div class="instance-tags">
        <span class="badge blue">${device.profile_code || '未设置 code'}</span>
        ${device.is_custom || [device.brand, device.manufacturer, device.model].some(Boolean) ? '<span class="badge amber">自定义机型</span>' : ''}
        ${item.adb_port ? `<span class="badge neutral">ADB ${item.adb_port}</span>` : ''}
      </div>
      <div class="instance-device">${deviceText}</div>
      <div class="instance-meta"><span>${item.width || 0}×${item.height || 0}</span><span>DPI ${item.dpi || 0}</span><span>${item.instance_dir || '未定位实例目录'}</span></div>
      ${warnings.length ? `<div class="warning-mini">${icon('i-warning')}<span>${warnings.join('；')}</span></div>` : ''}
      <div class="instance-actions">
        <button class="btn small primary" data-action="root-on" data-instance="${item.instance_id}">${icon('i-root')}<span>开启 Root</span></button>
        <button class="btn small ghost" data-action="root-off" data-instance="${item.instance_id}">${icon('i-root')}<span>关闭 Root</span></button>
        <button class="btn small accent" data-action="edit-device" data-instance="${item.instance_id}">${icon('i-device')}<span>机型</span></button>
      </div>
    </article>`;
}

function renderInstances() {
  const grid = $('instance-grid');
  if (!state.instances.length) {
    grid.innerHTML = `<article class="card"><div class="card-head"><h2>未检测到实例</h2></div><p class="muted">请确认 BlueStacks 已安装，或在上方输入 bluestacks.conf 路径。</p></article>`;
  } else {
    grid.innerHTML = state.instances.map(instanceCard).join('');
  }
  renderSelectedCount();
}

function fillDeviceForm(device = {}) {
  $('device-profile-code').value = device.profile_code || '';
  $('device-manufacturer').value = device.manufacturer || '';
  $('device-brand').value = device.brand || '';
  $('device-model').value = device.model || '';
  $('device-width').value = device.width || '';
  $('device-height').value = device.height || '';
  $('device-dpi').value = device.dpi || '';
}

function collectDeviceForm() {
  return {
    profile_code: $('device-profile-code').value.trim(),
    manufacturer: $('device-manufacturer').value.trim(),
    brand: $('device-brand').value.trim(),
    model: $('device-model').value.trim(),
    width: $('device-width').value || null,
    height: $('device-height').value || null,
    dpi: $('device-dpi').value || null,
  };
}

function renderDevice() {
  const ids = selectedIds();
  const badge = $('device-selected-badge');
  badge.className = `badge ${ids.length ? 'green' : 'neutral'}`;
  badge.textContent = ids.length ? `已选择 ${ids.length} 个实例` : '未选择实例';
  const first = state.instances.find((item) => state.selected.has(item.instance_id));
  if (first) fillDeviceForm(first.device || {});
}

function renderPresets() {
  const grid = $('preset-grid');
  if (!state.presets.length) {
    grid.innerHTML = '<div class="muted">暂无内置机型</div>';
    return;
  }
  grid.innerHTML = state.presets.map((preset) => `
    <div class="preset-item" data-preset="${preset.code}">
      <div class="preset-name">${preset.label}</div>
      <div class="preset-code">${preset.code} · ${preset.width}×${preset.height} · DPI ${preset.dpi}</div>
      <div class="preset-code">${preset.manufacturer || '—'} / ${preset.brand || '—'} / ${preset.model || '—'}</div>
    </div>`).join('');
  $('profile-code-options').innerHTML = state.profileCodes.map((code) => `<option value="${code.code}">${code.label}</option>`).join('');
}

function renderBackups() {
  const list = $('backup-list');
  if (!state.backups.length) {
    list.innerHTML = '<div class="muted">暂无备份。修改配置会自动创建备份。</div>';
    return;
  }
  list.innerHTML = state.backups.map((backup) => `
    <div class="backup-item">
      <div><div class="backup-name">${backup.backup_id}</div><div class="backup-meta">${new Date(backup.created_at * 1000).toLocaleString()} · ${backup.size} 字节 · ${backup.original_path}</div></div>
      <div class="button-row"><button class="btn small secondary" data-restore="${backup.backup_id}">${icon('i-restore')}<span>恢复</span></button><button class="btn small danger" data-delete-backup="${backup.backup_id}">${icon('i-trash')}<span>删除</span></button></div>
    </div>`).join('');
}

function renderPreflight() {
  const result = state.preflight;
  const grid = $('preflight-grid');
  if (!result) {
    grid.innerHTML = '<article class="card check-card muted">点击“运行检查”查看状态</article>';
    $('preflight-warnings').innerHTML = '';
    return;
  }
  grid.innerHTML = (result.checks || []).map((check) => `
    <article class="card check-card">
      <div class="check-icon ${check.ok ? 'ok' : 'fail'}">${icon(check.ok ? 'i-check' : 'i-warning')}</div>
      <div><div class="check-title">${check.name}</div><div class="check-detail">${check.detail || ''}</div></div>
    </article>`).join('');
  $('preflight-warnings').innerHTML = (result.warnings || []).map((warning) => `<div class="warning-item">${icon('i-warning')}<span>${warning}</span></div>`).join('') || '<div class="muted">没有需要特别注意的警告。</div>';
}

function renderPlatform() {
  const platform = state.platform || {};
  const rows = [
    ['系统', `${platform.system || '—'} ${platform.release || ''}`],
    ['架构', platform.machine || '—'],
    ['Python', platform.python || '—'],
    ['BlueStacks 进程', (platform.bluestacks_processes || []).join(', ') || '未检测到'],
  ];
  $('platform-detail').innerHTML = rows.map(([key, value]) => `<div class="detail-row"><span class="key">${key}</span><span class="value">${value || '—'}</span></div>`).join('');
}

function renderHistory() {
  const list = $('history-list');
  const history = state.history || [];
  list.innerHTML = history.slice().reverse().map((entry) => `<div class="history-item"><strong>${entry.action}</strong> · ${JSON.stringify(entry.summary)}</div>`).join('') || '<div class="muted">暂无操作记录</div>';
}

async function loadState() {
  const [stateData, installations] = await Promise.all([
    api('/api/state'),
    api('/api/installations'),
  ]);
  state.platform = stateData.platform;
  state.history = stateData.history || [];
  state.tokenConfigured = Boolean(stateData.token_configured);
  state.installations = installations;
  renderTopbar();
  renderNav();
  renderPlatform();
  renderHistory();
  renderDashboard();
  renderInstances();
  renderDevice();
  return stateData;
}

async function loadInstances() {
  const query = state.configPath ? `?config_path=${encodeURIComponent(state.configPath)}` : '';
  state.instances = await api('/api/instances' + query);
  state.selected = new Set(state.instances.map((item) => item.instance_id).filter((id) => state.selected.has(id)));
  renderTopbar();
  renderNav();
  renderDashboard();
  renderInstances();
  renderDevice();
}

async function loadPresets() {
  const [presets, codes] = await Promise.all([api('/api/presets'), api('/api/profile-codes')]);
  state.presets = presets;
  state.profileCodes = codes;
  renderPresets();
}

async function loadBackups() {
  state.backups = await api('/api/backups' + (state.configPath ? `?config_path=${encodeURIComponent(state.configPath)}` : ''));
  renderBackups();
  renderDashboard();
}

async function loadPreflight(operation = 'modify') {
  const instanceIds = selectedIds();
  const params = new URLSearchParams({ operation });
  if (instanceIds.length) params.set('instance_ids', instanceIds.join(','));
  if (state.configPath) params.set('config_path', state.configPath);
  state.preflight = await api('/api/preflight?' + params.toString());
  renderPreflight();
  return state.preflight;
}

async function refreshAll() {
  try {
    await loadState();
    await Promise.all([loadInstances(), loadBackups(), loadPresets()]);
    setStatus('本地就绪', true);
    if (state.tokenConfigured && !state.token) {
      showTokenSetup('本地服务已配置访问令牌。请输入令牌以继续。');
    }
  } catch (error) {
    setStatus('连接异常', false);
    if (error.status === 401) showTokenSetup(error.message);
    else toast(error.message, 'error');
  }
}

function setStatus(text, ok) {
  const pill = $('nav-status');
  pill.classList.toggle('ok', ok);
  pill.querySelector('span:last-child').textContent = text;
}

function showTokenSetup(message = '') {
  openModal('设置本地访问令牌', `${message || '请设置一个令牌，用于保护本机 API。'}<br />设置后每次修改都会携带该令牌。`, '保存', async () => {
    const token = $('token-input').value.trim();
    if (!token) return;
    try {
      await api('/api/token', { method: 'POST', body: JSON.stringify({ token }) });
      state.token = token;
      localStorage.setItem('manager_token', token);
      closeModal();
      toast('访问令牌已保存', 'ok');
      await refreshAll();
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}

function openModal(title, body, confirmText = '确认', onConfirm, danger = false) {
  $('modal-title').textContent = title;
  $('modal-body').innerHTML = body;
  $('modal-confirm').textContent = confirmText;
  $('modal-confirm').className = `btn ${danger ? 'danger' : 'primary'}`;
  $('modal').classList.remove('hidden');
  $('modal-confirm').onclick = async () => {
    await onConfirm();
  };
}

function closeModal() {
  $('modal').classList.add('hidden');
  $('modal-confirm').onclick = null;
}

async function confirmRoot(instanceIds, enabled) {
  const text = enabled ? '开启' : '关闭';
  openModal(`${text} Root`, `将对以下实例修改 <code>enable_root_access</code>：<br />${instanceIds.join('、') || '未选择'}。<br /><br />每次修改前会自动创建备份。新版 BlueStacks 可能需要额外补丁，请自行验证应用内 Root。`, `${text} Root`, async () => {
    try {
      const result = await api('/api/root', { method: 'POST', body: JSON.stringify({ instance_ids: instanceIds, enabled, config_path: state.configPath || null, auto_backup: true }) });
      closeModal();
      toast(result.changed ? `已${text} ${instanceIds.length} 个实例` : '没有需要修改的配置', result.changed ? 'ok' : 'error');
      await refreshAll();
    } catch (error) {
      closeModal();
      toast(error.message, 'error');
    }
  }, !enabled);
}

async function applyDevice(device) {
  const ids = selectedIds();
  if (!ids.length) { toast('请先选择实例', 'error'); return; }
  try {
    const result = await api('/api/device', { method: 'POST', body: JSON.stringify({ instance_ids: ids, device, config_path: state.configPath || null, auto_backup: true }) });
    toast(result.changed ? `已更新 ${ids.length} 个实例机型` : '没有需要修改的配置', result.changed ? 'ok' : 'error');
    await refreshAll();
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function randomDevice() {
  const ids = selectedIds();
  if (!ids.length) { toast('请先选择实例', 'error'); return; }
  openModal('随机机型', `将为以下实例生成随机机型：<br />${ids.join('、')}。<br /><br />生成结果包含 manufacturer、brand、model、分辨率和 DPI。`, '应用随机机型', async () => {
    try {
      const result = await api('/api/device/random', { method: 'POST', body: JSON.stringify({ instance_ids: ids, config_path: state.configPath || null, auto_backup: true }) });
      closeModal();
      toast(result.changed ? '已应用随机机型' : '没有需要修改的配置', result.changed ? 'ok' : 'error');
      await refreshAll();
    } catch (error) {
      closeModal();
      toast(error.message, 'error');
    }
  });
}

async function restoreBackup(backupId) {
  openModal('恢复备份', `将用备份 <code>${backupId}</code> 覆盖当前配置文件。此操作不可撤销，建议先创建新备份。`, '恢复', async () => {
    try {
      await api(`/api/backup/${encodeURIComponent(backupId)}/restore`, { method: 'POST', body: JSON.stringify({ config_path: state.configPath || null }) });
      closeModal();
      toast('备份已恢复', 'ok');
      await refreshAll();
    } catch (error) {
      closeModal();
      toast(error.message, 'error');
    }
  }, true);
}

async function deleteBackup(backupId) {
  openModal('删除备份', `确认删除备份 <code>${backupId}</code>？此操作不可撤销。`, '删除', async () => {
    try {
      await api(`/api/backup/${encodeURIComponent(backupId)}/delete`, { method: 'POST', body: JSON.stringify({ config_path: state.configPath || null }) });
      closeModal();
      toast('备份已删除', 'ok');
      await loadBackups();
    } catch (error) {
      closeModal();
      toast(error.message, 'error');
    }
  }, true);
}

function bindEvents() {
  document.querySelectorAll('.nav-item').forEach((button) => button.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach((item) => item.classList.remove('active'));
    document.querySelectorAll('.view').forEach((view) => view.classList.remove('active'));
    button.classList.add('active');
    $('view-' + button.dataset.view).classList.add('active');
    $('page-title').textContent = button.textContent.trim();
    const subtitles = {
      dashboard: '本地检测 BlueStacks 安装与实例状态',
      instances: '批量管理 BlueStacks 实例',
      device: '修改机型、随机生成或手动填写',
      preflight: '在修改前检查路径、运行状态和备份',
      backups: '配置备份与恢复',
      settings: '令牌、路径与运行环境',
    };
    $('page-subtitle').textContent = subtitles[button.dataset.view] || '';
  }));
  $('btn-theme').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  $('btn-refresh').addEventListener('click', refreshAll);
  $('config-path').addEventListener('change', async (event) => {
    state.configPath = event.target.value.trim();
    localStorage.setItem('manager_config_path', state.configPath);
    await refreshAll();
  });
  $('check-all').addEventListener('change', async (event) => {
    if (event.target.checked) state.selected = new Set(state.instances.map((item) => item.instance_id));
    else state.selected.clear();
    renderInstances();
    renderDevice();
  });
  $('instance-grid').addEventListener('change', (event) => {
    if (event.target.matches('input[type="checkbox"]')) {
      const id = event.target.dataset.instance;
      if (event.target.checked) state.selected.add(id); else state.selected.delete(id);
      event.target.closest('.instance-card').classList.toggle('selected', event.target.checked);
      renderSelectedCount();
      renderDevice();
    }
  });
  $('instance-grid').addEventListener('click', async (event) => {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const id = button.dataset.instance;
    if (button.dataset.action === 'root-on') await confirmRoot([id], true);
    if (button.dataset.action === 'root-off') await confirmRoot([id], false);
    if (button.dataset.action === 'edit-device') {
      state.selected.clear();
      state.selected.add(id);
      await loadInstances();
      document.querySelector('[data-view="device"]').click();
    }
  });
  $('btn-enable-root').addEventListener('click', () => confirmRoot(selectedIds(), true));
  $('btn-disable-root').addEventListener('click', () => confirmRoot(selectedIds(), false));
  $('btn-random-device').addEventListener('click', randomDevice);
  $('btn-edit-device').addEventListener('click', async () => {
    if (!selectedIds().length) { toast('请先选择实例', 'error'); return; }
    document.querySelector('[data-view="device"]').click();
  });
  $('btn-apply-device').addEventListener('click', () => applyDevice(collectDeviceForm()));
  $('btn-random-form-device').addEventListener('click', async () => {
    try {
      const device = await api('/api/device/preview', { method: 'POST', body: JSON.stringify({ overrides: {} }) });
      fillDeviceForm(device);
      toast('已生成随机机型，可继续编辑后应用', 'ok');
    } catch (error) {
      toast(error.message, 'error');
    }
  });
  $('btn-clear-device').addEventListener('click', () => fillDeviceForm());
  $('btn-reload-presets').addEventListener('click', loadPresets);
  $('preset-grid').addEventListener('click', (event) => {
    const item = event.target.closest('.preset-item');
    if (!item) return;
    const preset = state.presets.find((entry) => entry.code === item.dataset.preset);
    if (preset) fillDeviceForm(preset);
  });
  $('btn-run-preflight').addEventListener('click', () => loadPreflight('modify').catch((error) => toast(error.message, 'error')));
  $('btn-open-preflight').addEventListener('click', () => {
    document.querySelector('[data-view="preflight"]').click();
    loadPreflight('modify').catch((error) => toast(error.message, 'error'));
  });
  $('btn-create-backup').addEventListener('click', async () => {
    try {
      await api('/api/backup', { method: 'POST', body: JSON.stringify({ config_path: state.configPath || null, note: '手动备份' }) });
      toast('备份已创建', 'ok');
      await loadBackups();
    } catch (error) { toast(error.message, 'error'); }
  });
  $('backup-list').addEventListener('click', (event) => {
    const restore = event.target.closest('[data-restore]');
    const deleteButton = event.target.closest('[data-delete-backup]');
    if (restore) restoreBackup(restore.dataset.restore);
    if (deleteButton) deleteBackup(deleteButton.dataset.deleteBackup);
  });
  $('btn-save-token').addEventListener('click', async () => {
    const token = $('token-input').value.trim();
    if (!token) { toast('请填写令牌', 'error'); return; }
    try {
      await api('/api/token', { method: 'POST', body: JSON.stringify({ token }) });
      state.token = token;
      localStorage.setItem('manager_token', token);
      toast('令牌已保存', 'ok');
      await refreshAll();
    } catch (error) { toast(error.message, 'error'); }
  });
  $('btn-save-config-path').addEventListener('click', async () => {
    state.configPath = $('settings-config-path').value.trim();
    localStorage.setItem('manager_config_path', state.configPath);
    await refreshAll();
  });
  $('btn-open-instances').addEventListener('click', () => document.querySelector('[data-view="instances"]').click());
  document.querySelectorAll('[data-close]').forEach((element) => element.addEventListener('click', closeModal));
  $('modal-cancel').addEventListener('click', closeModal);
}

async function init() {
  await loadIcons();
  await bootstrapTheme();
  await bootstrapToken();
  bindEvents();
  await refreshAll();
}

init().catch((error) => {
  document.body.insertAdjacentHTML('beforeend', `<div class="toast error" style="right:22px;bottom:22px;position:fixed;">${error.message}</div>`);
});
