import {
  DEFAULT_OLLAMA_URL,
  STORAGE_KEYS,
  DEFAULT_QUICK_TAGS,
  FILTER_LABELS,
  ROLE_LABELS,
  UTILITY_PANEL_LABELS,
  readStored,
  saveStored,
  cleanQuickTags,
  readQuickTags,
  restoreSelectValue,
  apiGet,
  apiPost,
  filenameFromDisposition,
  splitSegmentInput,
  parseSegments,
} from "./frontend/web_shared.js";
import { createProjectsModule } from "./frontend/web_projects.js";
import { createWorkspaceBrowserModule } from "./frontend/web_workspace.js";
import { createImageOpsModule } from "./frontend/web_image_ops.js";
import { createCaptionModule } from "./frontend/web_caption.js";
import { createEditorModule } from "./frontend/web_editor.js";
import { createBrowserModule } from "./frontend/web_browser.js";
import { createShellModule } from "./frontend/web_shell.js";
import { createBootstrapModule } from "./frontend/web_bootstrap.js";

const state = {
  workspace: null,
  itemStats: null,
  items: [],
  globalSegments: [],
  globalTagQuery: "",
  globalTagDragging: "",
  globalTagPointerDrag: null,
  globalTagSuppressClick: false,
  selectedName: "",
  batchSelectedNames: new Set(),
  batchSelectionAnchor: "",
  currentItem: null,
  filter: "all",
  itemFolderFilter: "",
  visibleItems: [],
  segmentQuery: "",
  listSearchMode: readStored(STORAGE_KEYS.listSearchMode, "phrase"),
  listSearchMatchMode: readStored(STORAGE_KEYS.listSearchMatchMode, "contains"),
  utilityPanel: readStored(STORAGE_KEYS.utilityPanel, "workspace"),
  utilityOpen: false,
  captionSettingsOpen: false,
  browserPath: "",
  browserParent: "",
  browserRoot: "",
  browserTarget: readStored(STORAGE_KEYS.workspaceBrowserTarget, "control1"),
  browserItems: [],
  browserMessage: "",
  viewMode: readStored(STORAGE_KEYS.viewMode, "two"),
  listThumbMode: readStored(STORAGE_KEYS.listThumbMode, "result"),
  currentText: "",
  captionSavedText: "",
  captionDirty: false,
  captionAutoSaveTimer: 0,
  captionAutoSavePromise: null,
  currentSegments: [],
  quickTags: [],
  quickTagsCollapsed: true,
  quickTagsDirty: false,
  quickTagClickTimer: null,
  quickTagDragIndex: null,
  aiStatus: null,
  promptTemplates: [],
  aiOptions: {
    local_models: [],
    default_local_model: "qwen3.5-4b",
    default_ollama_url: DEFAULT_OLLAMA_URL,
  },
  apiModels: [],
  apiModelMenuOpen: false,
  apiModelQuery: "",
  ollamaModels: [],
  ollamaModelMenuOpen: false,
  ollamaModelQuery: "",
  lastBatchSignature: "",
  lastImageProcessSignature: "",
  lastExportSignature: "",
  lastExportDownloadPath: "",
  exportDownloadRequested: false,
  aiPollTimer: null,
  aiPollInFlight: false,
  projects: [],
  currentProjectId: "",
  currentProjectName: "",
  projectQuery: "",
  projectSortMode: readStored(STORAGE_KEYS.projectSortMode, "updated"),
  themeMode: readStored(STORAGE_KEYS.themeMode, "auto"),
};

let renderTags = () => {};
let renderGlobalTags = () => {};
let flushCaptionAutosave = async () => true;

const refs = {
  workbenchShell: document.querySelector("#workbenchShell"),
  workbenchLayout: document.querySelector("#workbenchLayout"),
  utilityActions: document.querySelector("#utilityActions"),
  utilityPageShell: document.querySelector("#utilityPageShell"),
  leftPanelResizer: document.querySelector("#leftPanelResizer"),
  listViewerResizer: document.querySelector("#listViewerResizer"),
  utilityPageTitle: document.querySelector("#utilityPageTitle"),
  closeUtilityBtn: document.querySelector("#closeUtilityBtn"),
  themeModeGroup: document.querySelector("#themeModeGroup"),
  captionSettingsShell: document.querySelector("#captionSettingsShell"),
  rightPanelResizer: document.querySelector("#rightPanelResizer"),
  viewerEditorResizer: document.querySelector("#viewerEditorResizer"),
  captionGlobalResizer: document.querySelector("#captionGlobalResizer"),
  closeCaptionSettingsBtn: document.querySelector("#closeCaptionSettingsBtn"),
  control1Dir: document.querySelector("#control1Dir"),
  control2Dir: document.querySelector("#control2Dir"),
  control3Dir: document.querySelector("#control3Dir"),
  controlCount: document.querySelector("#controlCount"),
  ignoreTokensInput: document.querySelector("#ignoreTokensInput"),
  autoOpenLastWorkspace: document.querySelector("#autoOpenLastWorkspace"),
  resultDir: document.querySelector("#resultDir"),
  mergeControl1Dir: document.querySelector("#mergeControl1Dir"),
  mergeControl2Dir: document.querySelector("#mergeControl2Dir"),
  mergeControl3Dir: document.querySelector("#mergeControl3Dir"),
  mergeResultDir: document.querySelector("#mergeResultDir"),
  mergeWorkspaceBtn: document.querySelector("#mergeWorkspaceBtn"),
  mergeStatus: document.querySelector("#mergeStatus"),
  workspaceBrowserRoot: document.querySelector("#workspaceBrowserRoot"),
  workspaceBrowseBtn: document.querySelector("#workspaceBrowseBtn"),
  workspaceBrowseUpBtn: document.querySelector("#workspaceBrowseUpBtn"),
  workspaceBrowseUseBtn: document.querySelector("#workspaceBrowseUseBtn"),
  workspaceBrowserTargetGroup: document.querySelector("#workspaceBrowserTargetGroup"),
  workspaceBrowserPath: document.querySelector("#workspaceBrowserPath"),
  workspaceBrowserList: document.querySelector("#workspaceBrowserList"),
  loadWorkspaceBtn: document.querySelector("#loadWorkspaceBtn"),
  rescanWorkspaceBtn: document.querySelector("#rescanWorkspaceBtn"),
  saveProjectBtn: document.querySelector("#saveProjectBtn"),
  saveProjectAsBtn: document.querySelector("#saveProjectAsBtn"),
  refreshProjectsBtn: document.querySelector("#refreshProjectsBtn"),
  cleanupTmpBtn: document.querySelector("#cleanupTmpBtn"),
  projectNameInput: document.querySelector("#projectNameInput"),
  projectSearchInput: document.querySelector("#projectSearchInput"),
  projectSortMode: document.querySelector("#projectSortMode"),
  projectGrid: document.querySelector("#projectGrid"),
  projectStatus: document.querySelector("#projectStatus"),
  workspaceStat: document.querySelector("#workspaceStat"),
  aiStat: document.querySelector("#aiStat"),
  focusStat: document.querySelector("#focusStat"),
  captionBackend: document.querySelector("#captionBackend"),
  captionBackendTabs: document.querySelector("#captionBackendTabs"),
  openCaptionSettingsBtn: document.querySelector("#openCaptionSettingsBtn"),
  overviewCurrentName: document.querySelector("#overviewCurrentName"),
  overviewCurrentMeta: document.querySelector("#overviewCurrentMeta"),
  metricAll: document.querySelector("#metricAll"),
  metricControlImages: document.querySelector("#metricControlImages"),
  metricResultImages: document.querySelector("#metricResultImages"),
  metricTxt: document.querySelector("#metricTxt"),
  metricIssues: document.querySelector("#metricIssues"),
  metricFiltered: document.querySelector("#metricFiltered"),
  localAiSummary: document.querySelector("#localAiSummary"),
  apiAiSummary: document.querySelector("#apiAiSummary"),
  ollamaAiSummary: document.querySelector("#ollamaAiSummary"),
  localAiStatusText: document.querySelector("#localAiStatusText"),
  apiAiStatusText: document.querySelector("#apiAiStatusText"),
  ollamaAiStatusText: document.querySelector("#ollamaAiStatusText"),
  filterGroup: document.querySelector("#filterGroup"),
  listThumbModeSelect: document.querySelector("#listThumbModeSelect"),
  tagSearch: document.querySelector("#tagSearch"),
  tagSearchModeGroup: document.querySelector("#tagSearchModeGroup"),
  tagSearchMatchGroup: document.querySelector("#tagSearchMatchGroup"),
  tagSearchClear: document.querySelector("#tagSearchClear"),
  itemList: document.querySelector("#itemList"),
  itemFolderFilters: document.querySelector("#itemFolderFilters"),
  listStats: document.querySelector("#listStats"),
  currentName: document.querySelector("#currentName"),
  currentMeta: document.querySelector("#currentMeta"),
  viewModeGroup: document.querySelector("#viewModeGroup"),
  viewerGrid: document.querySelector("#viewerGrid"),
  viewerTargetPixels: document.querySelector("#viewerTargetPixels"),
  viewerScaleBtn: document.querySelector("#viewerScaleBtn"),
  viewerMatchResultBtn: document.querySelector("#viewerMatchResultBtn"),
  captionEditor: document.querySelector("#captionEditor"),
  captionHighlight: document.querySelector("#captionHighlight"),
  tagChips: document.querySelector("#tagChips"),
  newTagInput: document.querySelector("#newTagInput"),
  addTagBtn: document.querySelector("#addTagBtn"),
  quickTagGrid: document.querySelector("#quickTagGrid"),
  quickTagPanel: document.querySelector("#quickTagPanel"),
  quickTagToggleBtn: document.querySelector("#quickTagToggleBtn"),
  quickTagSaveBtn: document.querySelector("#quickTagSaveBtn"),
  translateCurrentBtn: document.querySelector("#translateCurrentBtn"),
  translatedText: document.querySelector("#translatedText"),
  globalTagSearch: document.querySelector("#globalTagSearch"),
  globalTagList: document.querySelector("#globalTagList"),
  globalTagCount: document.querySelector("#globalTagCount"),
  batchAddInput: document.querySelector("#batchAddInput"),
  batchDeleteInput: document.querySelector("#batchDeleteInput"),
  batchReplaceOld: document.querySelector("#batchReplaceOld"),
  batchReplaceNew: document.querySelector("#batchReplaceNew"),
  batchAddBeforeBtn: document.querySelector("#batchAddBeforeBtn"),
  batchAddAfterBtn: document.querySelector("#batchAddAfterBtn"),
  batchDeleteBtn: document.querySelector("#batchDeleteBtn"),
  batchReplaceBtn: document.querySelector("#batchReplaceBtn"),
  batchRenameAddInput: document.querySelector("#batchRenameAddInput"),
  batchRenameAddPrefixBtn: document.querySelector("#batchRenameAddPrefixBtn"),
  batchRenameAddSuffixBtn: document.querySelector("#batchRenameAddSuffixBtn"),
  batchRenameDeleteInput: document.querySelector("#batchRenameDeleteInput"),
  batchRenameDeleteBtn: document.querySelector("#batchRenameDeleteBtn"),
  batchRenameReplaceOld: document.querySelector("#batchRenameReplaceOld"),
  batchRenameReplaceNew: document.querySelector("#batchRenameReplaceNew"),
  batchRenameReplaceBtn: document.querySelector("#batchRenameReplaceBtn"),
  deleteCurrentBtn: document.querySelector("#deleteCurrentBtn"),
  swapControlDir: document.querySelector("#swapControlDir"),
  swapResultDir: document.querySelector("#swapResultDir"),
  swapSuffix: document.querySelector("#swapSuffix"),
  swapPairsBtn: document.querySelector("#swapPairsBtn"),
  exportTargetPixels: document.querySelector("#exportTargetPixels"),
  exportSizeMultiple: document.querySelector("#exportSizeMultiple"),
  exportProjectName: document.querySelector("#exportProjectName"),
  exportFormat: document.querySelector("#exportFormat"),
  exportOutputDir: document.querySelector("#exportOutputDir"),
  exportProcessImages: document.querySelector("#exportProcessImages"),
  exportIncludeControls: document.querySelector("#exportIncludeControls"),
  exportPreserveSubfolders: document.querySelector("#exportPreserveSubfolders"),
  processProjectName: document.querySelector("#processProjectName"),
  processIncludeControls: document.querySelector("#processIncludeControls"),
  processLoadWorkspace: document.querySelector("#processLoadWorkspace"),
  processOnlyMismatched: document.querySelector("#processOnlyMismatched"),
  processImagesBtn: document.querySelector("#processImagesBtn"),
  processMatchResultBtn: document.querySelector("#processMatchResultBtn"),
  exportDatasetBtn: document.querySelector("#exportDatasetBtn"),
  aiModel: document.querySelector("#aiModel"),
  overwriteMode: document.querySelector("#overwriteMode"),
  captionMode: document.querySelector("#captionMode"),
  maxTokens: document.querySelector("#maxTokens"),
  customPrompt: document.querySelector("#customPrompt"),
  localModelMeta: document.querySelector("#localModelMeta"),
  localPromptLabel: document.querySelector("#localPromptLabel"),
  localPromptModeHint: document.querySelector("#localPromptModeHint"),
  installDepsBtn: document.querySelector("#installDepsBtn"),
  loadModelBtn: document.querySelector("#loadModelBtn"),
  validateLocalBtn: document.querySelector("#validateLocalBtn"),
  captionCurrentBtn: document.querySelector("#captionCurrentBtn"),
  captionBatchBtn: document.querySelector("#captionBatchBtn"),
  stopBatchBtn: document.querySelector("#stopBatchBtn"),
  apiBaseUrl: document.querySelector("#apiBaseUrl"),
  apiKey: document.querySelector("#apiKey"),
  apiModelPicker: document.querySelector("#apiModelPicker"),
  apiModelName: document.querySelector("#apiModelName"),
  apiModelMenuBtn: document.querySelector("#apiModelMenuBtn"),
  apiModelMenu: document.querySelector("#apiModelMenu"),
  apiModelSearch: document.querySelector("#apiModelSearch"),
  apiModelList: document.querySelector("#apiModelList"),
  apiOverwriteMode: document.querySelector("#apiOverwriteMode"),
  apiCaptionMode: document.querySelector("#apiCaptionMode"),
  apiMaxTokens: document.querySelector("#apiMaxTokens"),
  apiPrompt: document.querySelector("#apiPrompt"),
  apiPromptLabel: document.querySelector("#apiPromptLabel"),
  apiPromptModeHint: document.querySelector("#apiPromptModeHint"),
  loadApiModelsBtn: document.querySelector("#loadApiModelsBtn"),
  validateApiBtn: document.querySelector("#validateApiBtn"),
  ollamaBaseUrl: document.querySelector("#ollamaBaseUrl"),
  ollamaModelPicker: document.querySelector("#ollamaModelPicker"),
  ollamaModelName: document.querySelector("#ollamaModelName"),
  ollamaModelMenuBtn: document.querySelector("#ollamaModelMenuBtn"),
  ollamaModelMenu: document.querySelector("#ollamaModelMenu"),
  ollamaModelSearch: document.querySelector("#ollamaModelSearch"),
  ollamaModelList: document.querySelector("#ollamaModelList"),
  ollamaOverwriteMode: document.querySelector("#ollamaOverwriteMode"),
  ollamaCaptionMode: document.querySelector("#ollamaCaptionMode"),
  ollamaMaxTokens: document.querySelector("#ollamaMaxTokens"),
  ollamaPrompt: document.querySelector("#ollamaPrompt"),
  ollamaPromptLabel: document.querySelector("#ollamaPromptLabel"),
  ollamaPromptModeHint: document.querySelector("#ollamaPromptModeHint"),
  loadOllamaModelsBtn: document.querySelector("#loadOllamaModelsBtn"),
  validateOllamaBtn: document.querySelector("#validateOllamaBtn"),
  topAiProgressBar: document.querySelector("#topAiProgressBar"),
  topAiProgressText: document.querySelector("#topAiProgressText"),
  aiProgressBar: document.querySelector("#aiProgressBar"),
  aiStatusLine: document.querySelector("#aiStatusLine"),
};

function createAppDialog() {
  const root = document.querySelector("#appDialog");
  const title = document.querySelector("#appDialogTitle");
  const message = document.querySelector("#appDialogMessage");
  const input = document.querySelector("#appDialogInput");
  const cancelBtn = document.querySelector("#appDialogCancel");
  const confirmBtn = document.querySelector("#appDialogConfirm");
  let resolver = null;
  let dialogKind = "alert";
  let previousFocus = null;
  let closeTimer = 0;

  function finish(value) {
    if (!resolver || !root) return;
    const resolve = resolver;
    resolver = null;
    root.classList.remove("dialog-open");
    root.classList.add("dialog-closing");
    if (closeTimer) window.clearTimeout(closeTimer);
    closeTimer = window.setTimeout(() => {
      closeTimer = 0;
      root.setAttribute("aria-hidden", "true");
      root.classList.remove("dialog-closing");
      document.body.classList.remove("dialog-open");
      input.value = "";
      if (previousFocus?.focus) previousFocus.focus();
      resolve(value);
    }, 180);
  }

  function open({ kind = "alert", titleText = "提示", messageText = "", defaultValue = "" } = {}) {
    if (!root || !title || !message || !input || !cancelBtn || !confirmBtn) {
      return Promise.resolve(kind === "prompt" ? null : kind === "confirm" ? false : true);
    }
    if (resolver) {
      const resolvePrevious = resolver;
      resolver = null;
      resolvePrevious(kind === "prompt" ? null : false);
    }
    if (closeTimer) {
      window.clearTimeout(closeTimer);
      closeTimer = 0;
    }
    dialogKind = kind;
    previousFocus = document.activeElement;
    title.textContent = titleText || "提示";
    message.textContent = messageText || "";
    input.hidden = kind !== "prompt";
    input.value = defaultValue || "";
    cancelBtn.hidden = kind === "alert";
    root.dataset.kind = kind;
    root.setAttribute("aria-hidden", "false");
    root.classList.remove("dialog-closing");
    document.body.classList.add("dialog-open");
    return new Promise((resolve) => {
      resolver = resolve;
      requestAnimationFrame(() => {
        root.classList.add("dialog-open");
        const target = kind === "prompt" ? input : confirmBtn;
        target.focus();
        if (kind === "prompt") input.select();
      });
    });
  }

  confirmBtn?.addEventListener("click", () => {
    finish(dialogKind === "prompt" ? input.value : true);
  });
  cancelBtn?.addEventListener("click", () => {
    finish(dialogKind === "prompt" ? null : false);
  });
  root?.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      finish(dialogKind === "alert" ? true : dialogKind === "prompt" ? null : false);
    }
    if (event.key === "Enter" && dialogKind === "prompt" && document.activeElement === input) {
      event.preventDefault();
      finish(input.value);
    }
  });

  return {
    alert(messageText, titleText = "提示") {
      return open({ kind: "alert", titleText, messageText });
    },
    confirm(messageText, titleText = "确认") {
      return open({ kind: "confirm", titleText, messageText });
    },
    prompt(titleText, defaultValue = "") {
      return open({ kind: "prompt", titleText, defaultValue });
    },
  };
}

const appDialog = createAppDialog();
window.appAlert = (message, title) => appDialog.alert(message, title);
window.appConfirm = (message, title) => appDialog.confirm(message, title);
window.appPrompt = (title, defaultValue) => appDialog.prompt(title, defaultValue);

function saveQuickTags() {
  state.quickTags = cleanQuickTags(state.quickTags);
  saveStored(STORAGE_KEYS.quickTags, JSON.stringify(state.quickTags));
  state.quickTagsDirty = false;
  if (refs.quickTagSaveBtn) {
    refs.quickTagSaveBtn.title = "已存储";
    window.setTimeout(() => {
      refs.quickTagSaveBtn.title = "";
    }, 700);
  }
  renderQuickTags();
}

function syncSegmentsFromText() {
  state.currentSegments = parseSegments(state.currentText);
}

function syncCaptionDirty() {
  state.captionDirty = state.currentText !== state.captionSavedText;
}

function normalizeCaptionText(text) {
  return `${text || ""}`
    .replace(/[，,]/g, ",")
    .replace(/(?:,\s*){2,}/g, ", ")
    .replace(/,\s*/g, ", ");
}

function normalizeCaptionInputText(text) {
  return `${text || ""}`
    .replace(/，/g, ",")
    .replace(/(?:,\s*){2,}/g, ", ");
}

function setCaptionEditorText(text, { markSaved = false } = {}) {
  state.currentText = normalizeCaptionText(text);
  if (refs.captionEditor) refs.captionEditor.value = state.currentText;
  syncSegmentsFromText();
  if (markSaved) {
    state.captionSavedText = state.currentText;
    state.captionDirty = false;
  } else {
    syncCaptionDirty();
  }
}

async function confirmDiscardCaptionChanges() {
  return await flushCaptionAutosave();
}

function visibleNames() {
  const items = Array.isArray(state.visibleItems) ? state.visibleItems : state.items;
  return items.map((item) => item.name);
}

function syncBottomStatusTooltips() {
  document.querySelectorAll(".bottom-status-item").forEach((item) => {
    const baseTip = item.dataset.tooltip || item.getAttribute("title") || "";
    const label = item.querySelector("span")?.textContent.trim() || "";
    const value = item.querySelector("strong")?.textContent.trim() || "";
    const currentText = label && value ? `${label}：${value}` : label || value;
    const title = [currentText, baseTip].filter(Boolean).join("\n");
    item.dataset.tooltip = baseTip;
    item.setAttribute("title", title);
    item.setAttribute("aria-label", title.replace(/\n/g, "，"));
  });
}

const themeMediaQuery = window.matchMedia?.("(prefers-color-scheme: dark)");

function normalizeThemeMode(mode) {
  return ["auto", "light", "dark"].includes(mode) ? mode : "auto";
}

function resolveThemeMode(mode) {
  const normalized = normalizeThemeMode(mode);
  if (normalized === "auto") return themeMediaQuery?.matches ? "dark" : "light";
  return normalized;
}

function renderThemeMode() {
  const mode = normalizeThemeMode(state.themeMode);
  const resolved = resolveThemeMode(mode);
  document.documentElement.dataset.themeMode = mode;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved;
  refs.themeModeGroup?.querySelectorAll("button[data-theme-mode]").forEach((button) => {
    const isActive = button.dataset.themeMode === mode;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
}

function setThemeMode(mode, { persist = true } = {}) {
  state.themeMode = normalizeThemeMode(mode);
  if (persist) saveStored(STORAGE_KEYS.themeMode, state.themeMode);
  renderThemeMode();
}

refs.themeModeGroup?.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-theme-mode]");
  if (!button) return;
  setThemeMode(button.dataset.themeMode);
});

themeMediaQuery?.addEventListener?.("change", () => {
  if (state.themeMode === "auto") renderThemeMode();
});

renderThemeMode();

const bottomStatusTooltipObserver = new MutationObserver(syncBottomStatusTooltips);
document.querySelectorAll(".bottom-status-item").forEach((item) => {
  bottomStatusTooltipObserver.observe(item, { childList: true, subtree: true, characterData: true });
});
syncBottomStatusTooltips();

function showError(error) {
  console.error(error);
  window.appAlert(error.message || String(error), "错误");
}

function activeControlCount() {
  const rawCount = refs.controlCount?.value ?? state.workspace?.settings?.control_count ?? 1;
  const count = Number(rawCount);
  return Math.max(0, Math.min(3, Number.isFinite(count) ? count : 1));
}

const shellModule = createShellModule({
  state,
  refs,
  UTILITY_PANEL_LABELS,
  STORAGE_KEYS,
  saveStored,
  readStored,
  getLocalCaptionPayload: () => localCaptionPayload(),
  getApiCaptionPayload: () => apiCaptionPayload(),
  getOllamaCaptionPayload: () => ollamaCaptionPayload(),
});
const {
  renderUtilityPanelState,
  setUtilityPanel,
  closeUtilityPanel,
  toggleCaptionSettingsPanel,
  setAiStatusLine,
  runWithStatus,
  activeCaptionBackend,
  activeCaptionBackendLabel,
  activeCaptionPayload,
} = shellModule;

const {
  setWorkspaceBrowserTarget,
  seedWorkspaceBrowserRootFromInputs,
  syncWorkspaceBrowserTargetVisibility,
  applyWorkspaceBrowserPath,
  resolveWorkspaceInputPath,
  workspacePathRelativeToBrowserRoot,
  renderWorkspaceBrowser,
  browseWorkspacePath,
} = createWorkspaceBrowserModule({
  state,
  refs,
  ROLE_LABELS,
  STORAGE_KEYS,
  saveStored,
  apiGet,
  showError,
  activeControlCount,
});

const browserModule = createBrowserModule({
  state,
  refs,
  STORAGE_KEYS,
  FILTER_LABELS,
  ROLE_LABELS,
  saveStored,
  apiGet,
  apiPost,
  showError,
  confirmDiscardCaptionChanges,
  setCaptionEditorText,
  renderTags: (...args) => renderTags(...args),
  renderGlobalTags: (...args) => renderGlobalTags(...args),
  seedWorkspaceBrowserRootFromInputs,
  syncWorkspaceBrowserTargetVisibility,
  resolveWorkspaceInputPath,
  workspacePathRelativeToBrowserRoot,
  renderWorkspaceBrowser,
  closeUtilityPanel,
  setAiStatusLine,
});
const {
  renderWorkspaceSummary,
  renderFilters,
  renderItemList,
  renderViewer,
  shouldIgnoreListArrowNavigation,
  scrollSelectedItemIntoView,
  selectRelativeItem,
  refreshItems,
  selectItem,
  applyWorkspaceSummary,
  loadWorkspace,
  rescanWorkspace,
  mergeWorkspace,
  updateControlFieldVisibility,
} = browserModule;

const {
  renderProjects,
  refreshProjects,
  applyProjectUiState,
  saveCurrentProject,
  saveProjectAsNew,
  saveOpenProjectUiState,
  cleanupTmpNow,
} = createProjectsModule({
  state,
  refs,
  apiGet,
  apiPost,
  runWithStatus,
  showError,
  applyWorkspaceSummary,
  refreshItems,
  renderWorkspaceSummary,
  closeUtilityPanel,
  saveStored,
  STORAGE_KEYS,
  renderQuickTags: (...args) => renderQuickTags(...args),
  renderOverwriteModeHints: (...args) => renderOverwriteModeHints(...args),
  selectItem,
  saveCurrentCaption: (...args) => saveCurrentCaption(...args),
});

const editorModule = createEditorModule({
  state,
  refs,
  STORAGE_KEYS,
  saveStored,
  cleanQuickTags,
  splitSegmentInput,
  apiGet,
  apiPost,
  setAiStatusLine,
  refreshItems,
  applyWorkspaceSummary,
  visibleNames,
  renderViewer,
  confirmDiscardCaptionChanges,
  setCaptionEditorText,
  normalizeCaptionText,
  normalizeCaptionInputText,
  syncSegmentsFromText,
  syncCaptionDirty,
  onGlobalTagClick: (segment) => {
    state.segmentQuery = segment;
    state.listSearchMode = "phrase";
    saveStored(STORAGE_KEYS.listSearchMode, state.listSearchMode);
    refs.tagSearch.value = segment;
    refs.tagSearch.dispatchEvent(new Event("input", { bubbles: true }));
    refs.tagSearchModeGroup?.querySelectorAll("button[data-search-mode]").forEach((button) => {
      const isActive = button.dataset.searchMode === state.listSearchMode;
      button.classList.toggle("active", isActive);
      button.setAttribute("aria-pressed", String(isActive));
    });
    refs.tagSearchMatchGroup?.querySelectorAll("button[data-search-match]").forEach((button) => {
      const isActive = button.dataset.searchMatch === state.listSearchMatchMode;
      button.classList.toggle("active", isActive);
      button.setAttribute("aria-pressed", String(isActive));
    });
    refs.tagSearch.placeholder = "搜索 caption 短语";
    refreshItems().catch(showError);
  },
});
const {
  renderPromptTemplateSelectors,
  templateById,
  appendSegmentsToCaption,
  toggleQuickTags,
  renderQuickTags,
  saveCurrentCaption,
  scheduleCaptionAutosave,
  flushCaptionAutosave: editorFlushCaptionAutosave,
  translateCurrent,
  batchAdd,
  batchDelete,
  batchReplace,
  batchRename,
  swapControlResultPairs,
  deleteCurrent,
  loadPromptTemplates,
  savePromptTemplateFor,
  deletePromptTemplate,
} = editorModule;
renderTags = editorModule.renderTags;
renderGlobalTags = editorModule.renderGlobalTags;
flushCaptionAutosave = editorFlushCaptionAutosave;

const {
  renderImageProcessStatus,
  processImages,
  processMatchResultSizes,
  scaleViewerItem,
  matchViewerControlsToResult,
  exportDataset,
} = createImageOpsModule({
  state,
  refs,
  apiPost,
  pollAiStatus: (...args) => pollAiStatus(...args),
  renderViewer,
  refreshItems,
  setAiStatusLine,
});

const captionModule = createCaptionModule({
  state,
  refs,
  STORAGE_KEYS,
  DEFAULT_OLLAMA_URL,
  readStored,
  saveStored,
  restoreSelectValue,
  apiGet,
  apiPost,
  filenameFromDisposition,
  setAiStatusLine,
  activeCaptionBackendLabel,
  renderImageProcessStatus,
  refreshItems,
  selectItem,
  visibleNames,
  applyWorkspaceSummary,
  renderViewer,
  renderTags,
  setCaptionEditorText,
});
const {
  renderLocalModelMeta,
  renderOverwriteModeHints,
  renderLocalModelOptions,
  renderOllamaSuggestions,
  openApiModelMenu,
  closeApiModelMenu,
  renderApiModelSuggestions,
  openOllamaModelMenu,
  closeOllamaModelMenu,
  renderAiStatus,
  localCaptionPayload,
  apiCaptionPayload,
  ollamaCaptionPayload,
  loadModel,
  validateLocalModel,
  validateApiModel,
  validateOllamaModel,
  loadApiModels,
  loadOllamaModels,
  captionCurrentWithPayload,
  startBatchCaptionWithPayload,
  stopBatchCaption,
  installDeps,
  nextAiPollDelay,
  scheduleNextAiPoll,
  pollAiStatus,
  loadAiOptions,
  restoreCaptionSettings,
} = captionModule;

const { restorePersistedSettings, bindSettingsPersistence, bindEvents, bootstrap } = createBootstrapModule({
  state,
  refs,
  STORAGE_KEYS,
  DEFAULT_OLLAMA_URL,
  readStored,
  readQuickTags,
  saveStored,
  restoreSelectValue,
  apiGet,
  runWithStatus,
  showError,
  setUtilityPanel,
  toggleCaptionSettingsPanel,
  setAiStatusLine,
  activeCaptionBackendLabel,
  activeCaptionPayload,
  closeUtilityPanel,
  openApiModelMenu,
  closeApiModelMenu,
  renderApiModelSuggestions,
  openOllamaModelMenu,
  closeOllamaModelMenu,
  renderOllamaSuggestions,
  renderProjects,
  applyProjectUiState,
  renderViewer,
  renderTags,
  renderQuickTags,
  renderGlobalTags,
  renderFilters,
  renderWorkspaceSummary,
  applyWorkspaceSummary,
  renderAiStatus,
  renderOverwriteModeHints,
  renderWorkspaceBrowser,
  updateControlFieldVisibility,
  browseWorkspacePath,
  applyWorkspaceBrowserPath,
  setWorkspaceBrowserTarget,
  refreshItems,
  selectRelativeItem,
  shouldIgnoreListArrowNavigation,
  loadWorkspace,
  rescanWorkspace,
  saveCurrentProject,
  saveProjectAsNew,
  refreshProjects,
  cleanupTmpNow,
  scheduleCaptionAutosave,
  translateCurrent,
  batchAdd,
  batchDelete,
  batchReplace,
  batchRename,
  swapControlResultPairs,
  deleteCurrent,
  mergeWorkspace,
  scaleViewerItem,
  matchViewerControlsToResult,
  processImages,
  processMatchResultSizes,
  exportDataset,
  installDeps,
  loadModel,
  validateLocalModel,
  captionCurrentWithPayload,
  startBatchCaptionWithPayload,
  stopBatchCaption,
  loadApiModels,
  validateApiModel,
  loadOllamaModels,
  validateOllamaModel,
  nextAiPollDelay,
  scheduleNextAiPoll,
  pollAiStatus,
  loadAiOptions,
  loadPromptTemplates,
  savePromptTemplateFor,
  deletePromptTemplate,
  templateById,
  appendSegmentsToCaption,
  toggleQuickTags,
  saveQuickTags,
  setCaptionEditorText,
  normalizeCaptionText,
  normalizeCaptionInputText,
  syncSegmentsFromText,
  syncCaptionDirty,
  restoreCaptionSettings,
});

bootstrap().catch(showError);
