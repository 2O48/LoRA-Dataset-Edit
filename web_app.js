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
  apiPostDownload,
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
  selectedName: "",
  currentItem: null,
  filter: "all",
  segmentQuery: "",
  utilityPanel: window.localStorage.getItem(STORAGE_KEYS.utilityPanel) || "workspace",
  utilityOpen: false,
  browserPath: "",
  browserParent: "",
  browserTarget: window.localStorage.getItem(STORAGE_KEYS.workspaceBrowserTarget) || "control1",
  browserItems: [],
  browserMessage: "",
  viewMode: window.localStorage.getItem(STORAGE_KEYS.viewMode) || "two",
  currentText: "",
  captionSavedText: "",
  captionDirty: false,
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
  lastBatchSignature: "",
  lastImageProcessSignature: "",
  aiPollTimer: null,
  aiPollInFlight: false,
  projects: [],
  projectQuery: "",
  projectSortMode: window.localStorage.getItem(STORAGE_KEYS.projectSortMode) || "updated",
};

let renderTags = () => {};
let renderGlobalTags = () => {};

const refs = {
  workbenchShell: document.querySelector("#workbenchShell"),
  workbenchLayout: document.querySelector("#workbenchLayout"),
  utilityActions: document.querySelector("#utilityActions"),
  utilityPageShell: document.querySelector("#utilityPageShell"),
  utilityPageTitle: document.querySelector("#utilityPageTitle"),
  closeUtilityBtn: document.querySelector("#closeUtilityBtn"),
  control1Dir: document.querySelector("#control1Dir"),
  control2Dir: document.querySelector("#control2Dir"),
  control3Dir: document.querySelector("#control3Dir"),
  controlCount: document.querySelector("#controlCount"),
  ignoreTokensInput: document.querySelector("#ignoreTokensInput"),
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
  openCaptionSettingsBtn: document.querySelector("#openCaptionSettingsBtn"),
  overviewCurrentName: document.querySelector("#overviewCurrentName"),
  overviewCurrentMeta: document.querySelector("#overviewCurrentMeta"),
  metricAll: document.querySelector("#metricAll"),
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
  filterSummary: document.querySelector("#filterSummary"),
  tagSearch: document.querySelector("#tagSearch"),
  itemList: document.querySelector("#itemList"),
  listStats: document.querySelector("#listStats"),
  currentName: document.querySelector("#currentName"),
  currentMeta: document.querySelector("#currentMeta"),
  viewModeGroup: document.querySelector("#viewModeGroup"),
  viewerGrid: document.querySelector("#viewerGrid"),
  resolutionNote: document.querySelector("#resolutionNote"),
  viewerTargetPixels: document.querySelector("#viewerTargetPixels"),
  viewerScaleBtn: document.querySelector("#viewerScaleBtn"),
  viewerMatchResultBtn: document.querySelector("#viewerMatchResultBtn"),
  viewerProcessStatus: document.querySelector("#viewerProcessStatus"),
  captionEditor: document.querySelector("#captionEditor"),
  tagChips: document.querySelector("#tagChips"),
  newTagInput: document.querySelector("#newTagInput"),
  addTagBtn: document.querySelector("#addTagBtn"),
  quickTagGrid: document.querySelector("#quickTagGrid"),
  quickTagPanel: document.querySelector("#quickTagPanel"),
  quickTagToggleBtn: document.querySelector("#quickTagToggleBtn"),
  quickTagSaveBtn: document.querySelector("#quickTagSaveBtn"),
  saveTagsBtn: document.querySelector("#saveTagsBtn"),
  translateCurrentBtn: document.querySelector("#translateCurrentBtn"),
  translatedText: document.querySelector("#translatedText"),
  globalTagList: document.querySelector("#globalTagList"),
  globalTagCount: document.querySelector("#globalTagCount"),
  batchAddInput: document.querySelector("#batchAddInput"),
  batchDeleteInput: document.querySelector("#batchDeleteInput"),
  batchReplaceOld: document.querySelector("#batchReplaceOld"),
  batchReplaceNew: document.querySelector("#batchReplaceNew"),
  batchAddBtn: document.querySelector("#batchAddBtn"),
  batchDeleteBtn: document.querySelector("#batchDeleteBtn"),
  batchReplaceBtn: document.querySelector("#batchReplaceBtn"),
  deleteCurrentBtn: document.querySelector("#deleteCurrentBtn"),
  exportTargetPixels: document.querySelector("#exportTargetPixels"),
  exportSizeMultiple: document.querySelector("#exportSizeMultiple"),
  exportProjectName: document.querySelector("#exportProjectName"),
  exportFormat: document.querySelector("#exportFormat"),
  exportOutputDir: document.querySelector("#exportOutputDir"),
  exportProcessImages: document.querySelector("#exportProcessImages"),
  exportIncludeControls: document.querySelector("#exportIncludeControls"),
  processProjectName: document.querySelector("#processProjectName"),
  processIncludeControls: document.querySelector("#processIncludeControls"),
  processLoadWorkspace: document.querySelector("#processLoadWorkspace"),
  processOnlyMismatched: document.querySelector("#processOnlyMismatched"),
  processImagesBtn: document.querySelector("#processImagesBtn"),
  processMatchResultBtn: document.querySelector("#processMatchResultBtn"),
  processProgressBar: document.querySelector("#processProgressBar"),
  processStatus: document.querySelector("#processStatus"),
  exportDatasetBtn: document.querySelector("#exportDatasetBtn"),
  exportStatus: document.querySelector("#exportStatus"),
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
  ollamaModelName: document.querySelector("#ollamaModelName"),
  ollamaModelSuggestions: document.querySelector("#ollamaModelSuggestions"),
  ollamaOverwriteMode: document.querySelector("#ollamaOverwriteMode"),
  ollamaCaptionMode: document.querySelector("#ollamaCaptionMode"),
  ollamaMaxTokens: document.querySelector("#ollamaMaxTokens"),
  ollamaPrompt: document.querySelector("#ollamaPrompt"),
  ollamaPromptLabel: document.querySelector("#ollamaPromptLabel"),
  ollamaPromptModeHint: document.querySelector("#ollamaPromptModeHint"),
  loadOllamaModelsBtn: document.querySelector("#loadOllamaModelsBtn"),
  validateOllamaBtn: document.querySelector("#validateOllamaBtn"),
  aiProgressBar: document.querySelector("#aiProgressBar"),
  aiStatusLine: document.querySelector("#aiStatusLine"),
  aiLogPanel: document.querySelector("#aiLogPanel"),
};

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

function setCaptionEditorText(text, { markSaved = false } = {}) {
  state.currentText = `${text || ""}`;
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
  if (!state.captionDirty) return true;
  return window.confirm("当前 Caption 有未保存改动，继续操作会丢失改动。是否继续？");
}

function visibleNames() {
  return state.items.map((item) => item.name);
}

function showError(error) {
  console.error(error);
  window.alert(error.message || String(error));
}

function activeControlCount() {
  const count = Number(refs.controlCount?.value || state.workspace?.settings?.control_count || 1);
  return Math.max(1, Math.min(3, count));
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
  confirmDiscardCaptionChanges,
  setCaptionEditorText,
  renderTags: (...args) => renderTags(...args),
  renderGlobalTags: (...args) => renderGlobalTags(...args),
  seedWorkspaceBrowserRootFromInputs,
  syncWorkspaceBrowserTargetVisibility,
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
  saveCurrentProject,
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
  closeUtilityPanel,
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
  visibleNames,
  renderViewer,
  confirmDiscardCaptionChanges,
  setCaptionEditorText,
  syncSegmentsFromText,
  syncCaptionDirty,
  onGlobalTagClick: (segment) => {
    state.segmentQuery = segment;
    refs.tagSearch.value = segment;
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
  translateCurrent,
  batchAdd,
  batchDelete,
  batchReplace,
  deleteCurrent,
  loadPromptTemplates,
  savePromptTemplateFor,
  deletePromptTemplate,
} = editorModule;
renderTags = editorModule.renderTags;
renderGlobalTags = editorModule.renderGlobalTags;

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
  apiPostDownload,
  pollAiStatus: (...args) => pollAiStatus(...args),
  renderViewer,
  refreshItems,
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
  setAiStatusLine,
  activeCaptionBackendLabel,
  activeCaptionPayload,
  closeUtilityPanel,
  openApiModelMenu,
  closeApiModelMenu,
  renderApiModelSuggestions,
  renderProjects,
  renderViewer,
  renderTags,
  renderQuickTags,
  renderGlobalTags,
  renderFilters,
  renderWorkspaceSummary,
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
  refreshProjects,
  cleanupTmpNow,
  saveCurrentCaption,
  translateCurrent,
  batchAdd,
  batchDelete,
  batchReplace,
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
  syncSegmentsFromText,
  syncCaptionDirty,
  restoreCaptionSettings,
});

bootstrap().catch(showError);
