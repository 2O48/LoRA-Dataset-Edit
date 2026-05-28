export const DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434";

const STORAGE_NAMESPACE = "vds-ui";
const LEGACY_STORAGE_NAMESPACE = "lora-ui";

function storageKey(name) {
  return `${STORAGE_NAMESPACE}.${name}`;
}

function legacyStorageKey(key) {
  const currentPrefix = `${STORAGE_NAMESPACE}.`;
  if (!`${key || ""}`.startsWith(currentPrefix)) return `${key || ""}`;
  return `${LEGACY_STORAGE_NAMESPACE}.${key.slice(currentPrefix.length)}`;
}

export const STORAGE_KEYS = {
  utilityPanel: storageKey("utility-panel"),
  viewMode: storageKey("view-mode"),
  listThumbMode: storageKey("list-thumb-mode"),
  controlCount: storageKey("control-count"),
  ignoreTokens: storageKey("ignore-tokens"),
  autoOpenLastWorkspace: storageKey("auto-open-last-workspace"),
  lastWorkspaceDirs: storageKey("last-workspace-dirs"),
  workspaceBrowserRoot: storageKey("workspace-browser-root"),
  workspaceBrowserTarget: storageKey("workspace-browser-target"),
  exportTargetPixels: storageKey("export-target-pixels"),
  exportSizeMultiple: storageKey("export-size-multiple"),
  exportProjectName: storageKey("export-project-name"),
  exportFormat: storageKey("export-format"),
  exportOutputDir: storageKey("export-output-dir"),
  exportProcessImages: storageKey("export-process-images"),
  exportIncludeControls: storageKey("export-include-controls"),
  exportPreserveSubfolders: storageKey("export-preserve-subfolders"),
  viewerTargetPixels: storageKey("viewer-target-pixels"),
  processProjectName: storageKey("process-project-name"),
  processIncludeControls: storageKey("process-include-controls"),
  processLoadWorkspace: storageKey("process-load-workspace"),
  processOnlyMismatched: storageKey("process-only-mismatched"),
  swapControlDir: storageKey("swap-control-dir"),
  swapResultDir: storageKey("swap-result-dir"),
  swapSuffix: storageKey("swap-suffix"),
  quickTags: storageKey("quick-tags"),
  quickTagsCollapsed: storageKey("quick-tags-collapsed"),
  projectSortMode: storageKey("project-sort-mode"),
  themeMode: storageKey("theme-mode"),
  captionBackend: storageKey("caption-backend"),
  localModel: storageKey("local-model"),
  localOverwriteMode: storageKey("local-overwrite-mode"),
  localCaptionMode: storageKey("local-caption-mode"),
  localMaxTokens: storageKey("local-max-tokens"),
  localPrompt: storageKey("local-prompt"),
  apiBaseUrl: storageKey("api-base-url"),
  apiKey: storageKey("api-key"),
  apiModelName: storageKey("api-model-name"),
  apiOverwriteMode: storageKey("api-overwrite-mode"),
  apiCaptionMode: storageKey("api-caption-mode"),
  apiMaxTokens: storageKey("api-max-tokens"),
  apiPrompt: storageKey("api-prompt"),
  ollamaBaseUrl: storageKey("ollama-base-url"),
  ollamaModelName: storageKey("ollama-model-name"),
  ollamaOverwriteMode: storageKey("ollama-overwrite-mode"),
  ollamaCaptionMode: storageKey("ollama-caption-mode"),
  ollamaMaxTokens: storageKey("ollama-max-tokens"),
  ollamaPrompt: storageKey("ollama-prompt"),
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
  if (value !== null) return value;
  const legacyKey = legacyStorageKey(key);
  if (legacyKey && legacyKey !== key) {
    const legacyValue = window.localStorage.getItem(legacyKey);
    if (legacyValue !== null) {
      window.localStorage.setItem(key, legacyValue);
      return legacyValue;
    }
  }
  return fallback;
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
