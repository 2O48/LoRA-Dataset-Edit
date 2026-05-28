export const DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434";

export const STORAGE_KEYS = {
  utilityPanel: "lora-ui.utility-panel",
  viewMode: "lora-ui.view-mode",
  listThumbMode: "lora-ui.list-thumb-mode",
  controlCount: "lora-ui.control-count",
  ignoreTokens: "lora-ui.ignore-tokens",
  autoOpenLastWorkspace: "lora-ui.auto-open-last-workspace",
  lastWorkspaceDirs: "lora-ui.last-workspace-dirs",
  workspaceBrowserRoot: "lora-ui.workspace-browser-root",
  workspaceBrowserTarget: "lora-ui.workspace-browser-target",
  exportTargetPixels: "lora-ui.export-target-pixels",
  exportSizeMultiple: "lora-ui.export-size-multiple",
  exportProjectName: "lora-ui.export-project-name",
  exportFormat: "lora-ui.export-format",
  exportOutputDir: "lora-ui.export-output-dir",
  exportProcessImages: "lora-ui.export-process-images",
  exportIncludeControls: "lora-ui.export-include-controls",
  exportPreserveSubfolders: "lora-ui.export-preserve-subfolders",
  viewerTargetPixels: "lora-ui.viewer-target-pixels",
  processProjectName: "lora-ui.process-project-name",
  processIncludeControls: "lora-ui.process-include-controls",
  processLoadWorkspace: "lora-ui.process-load-workspace",
  processOnlyMismatched: "lora-ui.process-only-mismatched",
  swapControlDir: "lora-ui.swap-control-dir",
  swapResultDir: "lora-ui.swap-result-dir",
  swapSuffix: "lora-ui.swap-suffix",
  quickTags: "lora-ui.quick-tags",
  quickTagsCollapsed: "lora-ui.quick-tags-collapsed",
  projectSortMode: "lora-ui.project-sort-mode",
  themeMode: "lora-ui.theme-mode",
  captionBackend: "lora-ui.caption-backend",
  localModel: "lora-ui.local-model",
  localOverwriteMode: "lora-ui.local-overwrite-mode",
  localCaptionMode: "lora-ui.local-caption-mode",
  localMaxTokens: "lora-ui.local-max-tokens",
  localPrompt: "lora-ui.local-prompt",
  apiBaseUrl: "lora-ui.api-base-url",
  apiKey: "lora-ui.api-key",
  apiModelName: "lora-ui.api-model-name",
  apiOverwriteMode: "lora-ui.api-overwrite-mode",
  apiCaptionMode: "lora-ui.api-caption-mode",
  apiMaxTokens: "lora-ui.api-max-tokens",
  apiPrompt: "lora-ui.api-prompt",
  ollamaBaseUrl: "lora-ui.ollama-base-url",
  ollamaModelName: "lora-ui.ollama-model-name",
  ollamaOverwriteMode: "lora-ui.ollama-overwrite-mode",
  ollamaCaptionMode: "lora-ui.ollama-caption-mode",
  ollamaMaxTokens: "lora-ui.ollama-max-tokens",
  ollamaPrompt: "lora-ui.ollama-prompt",
};

export const DEFAULT_QUICK_TAGS = [
  "simple background",
  "white background",
  "transparent background",
  "studio lighting",
  "product photo",
  "close-up",
  "top-down view",
  "full body",
];

export const FILTER_LABELS = {
  all: "全部条目",
  no_control1: "缺控制 1",
  no_control2: "缺控制 2",
  no_control3: "缺控制 3",
  no_result: "缺结果",
  no_txt: "缺 TXT",
  res_mismatch: "分辨率异",
};

export const ROLE_LABELS = {
  control1: "控制图 1",
  control2: "控制图 2",
  control3: "控制图 3",
  result: "结果图",
};

export const UTILITY_PANEL_LABELS = {
  projects: "项目管理",
  workspace: "工作区设置",
  automation: "标注配置",
  batch: "批量",
  process: "图像预处理",
  export: "数据集导出",
};

export function readStored(key, fallback = "") {
  const value = window.localStorage.getItem(key);
  return value === null ? fallback : value;
}

export function saveStored(key, value) {
  window.localStorage.setItem(key, `${value ?? ""}`);
}

export function cleanQuickTags(values) {
  const next = [];
  const seen = new Set();
  for (const raw of Array.isArray(values) ? values : []) {
    const value = `${raw || ""}`;
    const key = value.toLowerCase();
    if (!value.trim() || seen.has(key)) continue;
    seen.add(key);
    next.push(value);
  }
  return next.length ? next : [...DEFAULT_QUICK_TAGS];
}

export function readQuickTags() {
  const raw = readStored(STORAGE_KEYS.quickTags, "");
  if (!raw) return [...DEFAULT_QUICK_TAGS];
  try {
    return cleanQuickTags(JSON.parse(raw));
  } catch (_) {
    return [...DEFAULT_QUICK_TAGS];
  }
}

export function restoreSelectValue(select, key, fallback) {
  const value = readStored(key, fallback);
  const allowed = Array.from(select.options).some((option) => option.value === value);
  select.value = allowed ? value : fallback;
}

export async function apiGet(path, params = null) {
  const url = new URL(path, window.location.origin);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    }
  }
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || `Request failed (${response.status})`);
  }
  return data;
}

export async function apiPost(path, payload = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || `Request failed (${response.status})`);
  }
  return data;
}

export async function apiPostDownload(path, payload = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const contentType = response.headers.get("Content-Type") || "";
  if (!response.ok) {
    if (contentType.includes("application/json")) {
      const data = await response.json();
      throw new Error(data.error || `Request failed (${response.status})`);
    }
    throw new Error(`Request failed (${response.status})`);
  }
  if (contentType.includes("application/json")) {
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "Request failed");
    return { type: "json", data };
  }
  return {
    type: "blob",
    blob: await response.blob(),
    filename: filenameFromDisposition(response.headers.get("Content-Disposition")) || "dataset.zip",
  };
}

export function filenameFromDisposition(value) {
  const encoded = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(value || "");
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1]);
    } catch (_) {
      return encoded[1];
    }
  }
  const match = /filename="?([^";]+)"?/i.exec(value || "");
  return match ? match[1] : "";
}

export function splitSegmentInput(value) {
  return `${value || ""}`
    .split(",")
    .map((segment) => segment.trim())
    .filter(Boolean);
}

export function parseSegments(value) {
  return `${value || ""}`
    .split(/[,\n;，；]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}
