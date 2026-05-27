export function createBootstrapModule({
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
  applyWorkspaceSummary,
  refreshItems,
  selectRelativeItem,
  shouldIgnoreListArrowNavigation,
  loadWorkspace,
  rescanWorkspace,
  saveCurrentProject,
  saveProjectAsNew,
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
  syncSegmentsFromText,
  syncCaptionDirty,
  restoreCaptionSettings,
}) {
  function restorePersistedSettings() {
    refs.controlCount.value = readStored(STORAGE_KEYS.controlCount, "1");
    refs.ignoreTokensInput.value = readStored(STORAGE_KEYS.ignoreTokens, "");
    if (refs.autoOpenLastWorkspace) {
      refs.autoOpenLastWorkspace.checked = readStored(STORAGE_KEYS.autoOpenLastWorkspace, "false") === "true";
    }
    refs.workspaceBrowserRoot.value = readStored(STORAGE_KEYS.workspaceBrowserRoot, "");
    restoreSelectValue(refs.exportTargetPixels, STORAGE_KEYS.exportTargetPixels, "4");
    restoreSelectValue(refs.exportSizeMultiple, STORAGE_KEYS.exportSizeMultiple, "16");
    refs.exportProjectName.value = readStored(STORAGE_KEYS.exportProjectName, "");
    refs.exportFormat.value = readStored(STORAGE_KEYS.exportFormat, refs.exportFormat.value);
    refs.exportOutputDir.value = readStored(STORAGE_KEYS.exportOutputDir, "");
    refs.exportProcessImages.checked = readStored(STORAGE_KEYS.exportProcessImages, "true") !== "false";
    refs.exportIncludeControls.checked = readStored(STORAGE_KEYS.exportIncludeControls, "true") !== "false";
    refs.viewerTargetPixels.value = readStored(STORAGE_KEYS.viewerTargetPixels, "4");
    refs.processProjectName.value = readStored(STORAGE_KEYS.processProjectName, "");
    refs.processIncludeControls.checked = readStored(STORAGE_KEYS.processIncludeControls, "true") !== "false";
    refs.processLoadWorkspace.checked = readStored(STORAGE_KEYS.processLoadWorkspace, "true") !== "false";
    refs.processOnlyMismatched.checked = readStored(STORAGE_KEYS.processOnlyMismatched, "true") !== "false";
    state.quickTags = readQuickTags();
    state.quickTagsCollapsed = readStored(STORAGE_KEYS.quickTagsCollapsed, "true") !== "false";
    state.quickTagsDirty = false;
    restoreCaptionSettings();
  }

  function bindSettingsPersistence() {
    const refreshModelStatus = () => renderAiStatus();
    refs.controlCount.addEventListener("change", () => {
      saveStored(STORAGE_KEYS.controlCount, refs.controlCount.value);
      updateControlFieldVisibility();
    });
    refs.ignoreTokensInput.addEventListener("change", () => {
      saveStored(STORAGE_KEYS.ignoreTokens, refs.ignoreTokensInput.value.trim());
    });
    refs.autoOpenLastWorkspace?.addEventListener("change", () => {
      saveStored(STORAGE_KEYS.autoOpenLastWorkspace, refs.autoOpenLastWorkspace.checked ? "true" : "false");
    });
    refs.workspaceBrowserRoot.addEventListener("change", () => {
      saveStored(STORAGE_KEYS.workspaceBrowserRoot, refs.workspaceBrowserRoot.value.trim());
    });
    refs.projectSortMode?.addEventListener("change", () => {
      state.projectSortMode = refs.projectSortMode.value;
      saveStored(STORAGE_KEYS.projectSortMode, state.projectSortMode);
      renderProjects();
    });
    refs.projectSearchInput?.addEventListener("input", () => {
      state.projectQuery = refs.projectSearchInput.value;
      renderProjects();
    });
    refs.exportTargetPixels.addEventListener("change", () => saveStored(STORAGE_KEYS.exportTargetPixels, refs.exportTargetPixels.value));
    refs.exportSizeMultiple.addEventListener("change", () => saveStored(STORAGE_KEYS.exportSizeMultiple, refs.exportSizeMultiple.value));
    refs.exportProjectName.addEventListener("change", () => saveStored(STORAGE_KEYS.exportProjectName, refs.exportProjectName.value.trim()));
    refs.exportFormat.addEventListener("change", () => saveStored(STORAGE_KEYS.exportFormat, refs.exportFormat.value));
    refs.exportOutputDir.addEventListener("change", () => saveStored(STORAGE_KEYS.exportOutputDir, refs.exportOutputDir.value.trim()));
    refs.exportProcessImages.addEventListener("change", () => saveStored(STORAGE_KEYS.exportProcessImages, refs.exportProcessImages.checked ? "true" : "false"));
    refs.exportIncludeControls.addEventListener("change", () => saveStored(STORAGE_KEYS.exportIncludeControls, refs.exportIncludeControls.checked ? "true" : "false"));
    refs.viewerTargetPixels.addEventListener("change", () => saveStored(STORAGE_KEYS.viewerTargetPixels, refs.viewerTargetPixels.value));
    refs.processProjectName.addEventListener("change", () => saveStored(STORAGE_KEYS.processProjectName, refs.processProjectName.value.trim()));
    refs.processIncludeControls.addEventListener("change", () => saveStored(STORAGE_KEYS.processIncludeControls, refs.processIncludeControls.checked ? "true" : "false"));
    refs.processLoadWorkspace.addEventListener("change", () => saveStored(STORAGE_KEYS.processLoadWorkspace, refs.processLoadWorkspace.checked ? "true" : "false"));
    refs.processOnlyMismatched.addEventListener("change", () => saveStored(STORAGE_KEYS.processOnlyMismatched, refs.processOnlyMismatched.checked ? "true" : "false"));

    refs.aiModel.addEventListener("change", () => {
      saveStored(STORAGE_KEYS.localModel, refs.aiModel.value);
      renderOverwriteModeHints();
      refreshModelStatus();
    });
    refs.overwriteMode.addEventListener("change", () => saveStored(STORAGE_KEYS.localOverwriteMode, refs.overwriteMode.value));
    refs.overwriteMode.addEventListener("change", renderOverwriteModeHints);
    refs.captionMode.addEventListener("change", () => saveStored(STORAGE_KEYS.localCaptionMode, refs.captionMode.value));
    refs.maxTokens.addEventListener("change", () => saveStored(STORAGE_KEYS.localMaxTokens, refs.maxTokens.value));
    refs.customPrompt.addEventListener("change", () => saveStored(STORAGE_KEYS.localPrompt, refs.customPrompt.value));

    function renderCaptionBackendTabs() {
      const backend = refs.captionBackend?.value || readStored(STORAGE_KEYS.captionBackend, "local");
      refs.captionBackendTabs?.querySelectorAll("button[data-caption-backend]").forEach((button) => {
        const isActive = button.dataset.captionBackend === backend;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-selected", String(isActive));
      });
      document.querySelectorAll("[data-caption-backend-panel]").forEach((panel) => {
        const isActive = panel.dataset.captionBackendPanel === backend;
        panel.classList.toggle("active", isActive);
        panel.hidden = !isActive;
      });
    }

    function setCaptionBackend(backend) {
      if (refs.captionBackend) refs.captionBackend.value = backend;
      saveStored(STORAGE_KEYS.captionBackend, backend);
      renderCaptionBackendTabs();
      setAiStatusLine(`当前标注引擎：${activeCaptionBackendLabel()}`);
      renderAiStatus();
    }

    refs.captionBackendTabs?.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-caption-backend]");
      if (!button) return;
      setCaptionBackend(button.dataset.captionBackend);
    });

    refs.captionBackend?.addEventListener("change", () => {
      setCaptionBackend(refs.captionBackend.value);
    });
    renderCaptionBackendTabs();

    refs.apiBaseUrl.addEventListener("change", () => saveStored(STORAGE_KEYS.apiBaseUrl, refs.apiBaseUrl.value.trim()));
    refs.apiKey.addEventListener("input", () => saveStored(STORAGE_KEYS.apiKey, refs.apiKey.value.trim()));
    refs.apiModelName.addEventListener("input", () => {
      saveStored(STORAGE_KEYS.apiModelName, refs.apiModelName.value.trim());
      refreshModelStatus();
    });
    refs.apiModelName.addEventListener("change", () => {
      saveStored(STORAGE_KEYS.apiModelName, refs.apiModelName.value.trim());
      refreshModelStatus();
    });
    refs.ollamaBaseUrl.addEventListener("change", () => saveStored(STORAGE_KEYS.ollamaBaseUrl, refs.ollamaBaseUrl.value.trim()));
    refs.ollamaModelName.addEventListener("input", () => {
      saveStored(STORAGE_KEYS.ollamaModelName, refs.ollamaModelName.value.trim());
      refreshModelStatus();
    });
    refs.ollamaModelName.addEventListener("change", () => {
      saveStored(STORAGE_KEYS.ollamaModelName, refs.ollamaModelName.value.trim());
      refreshModelStatus();
    });
  }

  function readLastWorkspaceOpenPayload() {
    const raw = readStored(STORAGE_KEYS.lastWorkspaceDirs, "");
    if (!raw) return null;
    try {
      const payload = JSON.parse(raw);
      if (!payload || typeof payload !== "object") return null;
      const hasDirectory = ["control1_dir", "control2_dir", "control3_dir", "result_dir"].some((key) => `${payload[key] || ""}`.trim());
      return hasDirectory ? payload : null;
    } catch (_) {
      return null;
    }
  }

  function applyLastWorkspaceOpenPayload(payload) {
    state.currentProjectId = `${payload.project_id || ""}`;
    state.currentProjectName = `${payload.project_name || ""}`;
    if (refs.projectNameInput && state.currentProjectName) refs.projectNameInput.value = state.currentProjectName;
    refs.control1Dir.value = `${payload.control1_dir || ""}`;
    refs.control2Dir.value = `${payload.control2_dir || ""}`;
    refs.control3Dir.value = `${payload.control3_dir || ""}`;
    refs.resultDir.value = `${payload.result_dir || ""}`;
    refs.controlCount.value = `${payload.control_count ?? refs.controlCount.value ?? "1"}`;
    refs.ignoreTokensInput.value = `${payload.ignore_tokens || ""}`;
    updateControlFieldVisibility();
  }

  function restoreCurrentProjectFromLastWorkspace(workspace) {
    const payload = readLastWorkspaceOpenPayload();
    if (!payload) return false;
    const dirs = workspace?.dirs || {};
    const sameWorkspace = [
      [dirs.control1 || "", payload.control1_dir || ""],
      [dirs.control2 || "", payload.control2_dir || ""],
      [dirs.control3 || "", payload.control3_dir || ""],
      [dirs.result || "", payload.result_dir || ""],
    ].some(([current, remembered]) => remembered && current === remembered);
    if (!sameWorkspace) return false;
    state.currentProjectId = `${payload.project_id || ""}`;
    state.currentProjectName = `${payload.project_name || ""}`;
    if (refs.projectNameInput && state.currentProjectName) refs.projectNameInput.value = state.currentProjectName;
    if (refs.projectStatus && state.currentProjectName) {
      refs.projectStatus.textContent = `当前项目：${state.currentProjectName} · 已载入 ${state.projects.length} 个项目`;
    }
    renderWorkspaceSummary();
    return Boolean(state.currentProjectId || state.currentProjectName);
  }

  function inferSingleProjectForCurrentWorkspace() {
    if (state.currentProjectId || state.currentProjectName) return false;
    if (!state.workspace?.counts?.all || state.projects.length !== 1) return false;
    const project = state.projects[0];
    state.currentProjectId = project.id || "";
    state.currentProjectName = project.name || project.id || "";
    if (refs.projectNameInput && state.currentProjectName) refs.projectNameInput.value = state.currentProjectName;
    if (refs.projectStatus && state.currentProjectName) {
      refs.projectStatus.textContent = `当前项目：${state.currentProjectName} · 已载入 ${state.projects.length} 个项目`;
    }
    const payload = readLastWorkspaceOpenPayload() || {};
    saveStored(STORAGE_KEYS.lastWorkspaceDirs, JSON.stringify({
      ...payload,
      project_id: state.currentProjectId,
      project_name: state.currentProjectName,
    }));
    renderWorkspaceSummary();
    return true;
  }

  async function openLastWorkspaceOnStartup() {
    if (!refs.autoOpenLastWorkspace?.checked) return false;
    const payload = readLastWorkspaceOpenPayload();
    if (!payload) return false;
    applyLastWorkspaceOpenPayload(payload);
    await runWithStatus("正在打开上次加载的数据目录...", async () => {
      await loadWorkspace();
      setAiStatusLine("已打开上次加载的数据目录。");
    });
    return true;
  }

  function bindEvents() {
    function numericCssVar(name, fallback) {
      const value = window.getComputedStyle(refs.workbenchShell).getPropertyValue(name).trim();
      const parsed = Number.parseFloat(value);
      return Number.isFinite(parsed) ? parsed : fallback;
    }

    function setPanelWidthVar(name, value, min, max) {
      const clamped = Math.max(min, Math.min(max, value));
      refs.workbenchShell.style.setProperty(name, `${Math.round(clamped)}px`);
      window.localStorage.setItem(`lora-ui.${name.replace(/^--/, "")}`, String(Math.round(clamped)));
    }

    function restorePanelWidthVar(name, fallback, min, max) {
      const stored = Number.parseFloat(window.localStorage.getItem(`lora-ui.${name.replace(/^--/, "")}`) || "");
      if (Number.isFinite(stored)) setPanelWidthVar(name, stored, min, max);
      else refs.workbenchShell.style.setProperty(name, `${fallback}px`);
    }

    function bindPanelResizer(handle, { cssVar, fallback, min, max, direction }) {
      if (!handle) return;
      handle.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        const startX = event.clientX;
        const startWidth = numericCssVar(cssVar, fallback);
        handle.classList.add("dragging");
        handle.setPointerCapture?.(event.pointerId);
        const onMove = (moveEvent) => {
          const delta = (moveEvent.clientX - startX) * direction;
          setPanelWidthVar(cssVar, startWidth + delta, min, max);
        };
        const onUp = () => {
          handle.classList.remove("dragging");
          document.removeEventListener("pointermove", onMove);
          document.removeEventListener("pointerup", onUp);
        };
        document.addEventListener("pointermove", onMove);
        document.addEventListener("pointerup", onUp, { once: true });
      });
    }

    restorePanelWidthVar("--left-panel-width", 300, 240, 620);
    restorePanelWidthVar("--right-panel-width", 320, 280, 680);
    bindPanelResizer(refs.leftPanelResizer, { cssVar: "--left-panel-width", fallback: 300, min: 240, max: 620, direction: 1 });
    bindPanelResizer(refs.rightPanelResizer, { cssVar: "--right-panel-width", fallback: 320, min: 280, max: 680, direction: -1 });

    refs.utilityActions.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-panel]");
      if (!button) return;
      if (state.utilityOpen && state.utilityPanel === button.dataset.panel) {
        closeUtilityPanel();
        return;
      }
      setUtilityPanel(button.dataset.panel);
    });

    refs.closeUtilityBtn.addEventListener("click", closeUtilityPanel);

    refs.workspaceBrowseBtn.addEventListener("click", () => {
      browseWorkspacePath().catch(showError);
    });
    refs.workspaceBrowseUpBtn.addEventListener("click", () => {
      if (!state.browserParent) return;
      browseWorkspacePath(state.browserParent).catch(showError);
    });
    refs.workspaceBrowseUseBtn.addEventListener("click", () => {
      applyWorkspaceBrowserPath(state.browserPath || refs.workspaceBrowserRoot.value);
    });
    refs.workspaceBrowserRoot.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      browseWorkspacePath().catch(showError);
    });
    refs.workspaceBrowserTargetGroup.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-browser-target]");
      if (!button) return;
      setWorkspaceBrowserTarget(button.dataset.browserTarget);
    });

    refs.apiModelMenuBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      state.apiModelMenuOpen ? closeApiModelMenu() : openApiModelMenu();
    });
    refs.apiModelName?.addEventListener("focus", () => {
      if (state.apiModels.length) openApiModelMenu({ focusSearch: false });
    });
    refs.apiModelSearch?.addEventListener("input", () => {
      state.apiModelQuery = refs.apiModelSearch.value.trim();
      renderApiModelSuggestions();
    });
    refs.apiModelSearch?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        const firstOption = refs.apiModelList?.querySelector(".model-picker-option");
        if (firstOption) firstOption.click();
      }
      if (event.key === "Escape") {
        event.preventDefault();
        closeApiModelMenu();
      }
    });
    refs.ollamaModelMenuBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      state.ollamaModelMenuOpen ? closeOllamaModelMenu() : openOllamaModelMenu();
    });
    refs.ollamaModelName?.addEventListener("focus", () => {
      if (state.ollamaModels.length) openOllamaModelMenu({ focusSearch: false });
    });
    refs.ollamaModelSearch?.addEventListener("input", () => {
      state.ollamaModelQuery = refs.ollamaModelSearch.value.trim();
      renderOllamaSuggestions();
    });
    refs.ollamaModelSearch?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        const firstOption = refs.ollamaModelList?.querySelector(".model-picker-option");
        if (firstOption) firstOption.click();
      }
      if (event.key === "Escape") {
        event.preventDefault();
        closeOllamaModelMenu();
      }
    });

    refs.loadWorkspaceBtn.addEventListener("click", () => runWithStatus("正在加载工作区...", () => loadWorkspace()).catch(showError));
    refs.rescanWorkspaceBtn.addEventListener("click", () => runWithStatus("正在重扫工作区...", () => rescanWorkspace()).catch(showError));
    refs.saveProjectBtn?.addEventListener("click", () => runWithStatus("正在保存项目...", () => saveCurrentProject()).catch(showError));
    refs.saveProjectAsBtn?.addEventListener("click", () => runWithStatus("正在保存为新项目...", () => saveProjectAsNew()).catch(showError));
    refs.refreshProjectsBtn?.addEventListener("click", () => runWithStatus("正在刷新项目列表...", () => refreshProjects()).catch(showError));
    refs.cleanupTmpBtn?.addEventListener("click", () => runWithStatus("正在清理 tmp...", () => cleanupTmpNow()).catch(showError));
    refs.openCaptionSettingsBtn?.addEventListener("click", () => toggleCaptionSettingsPanel());
    refs.closeCaptionSettingsBtn?.addEventListener("click", () => toggleCaptionSettingsPanel(false));

    refs.filterGroup.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-filter]");
      if (!button) return;
      state.filter = button.dataset.filter;
      renderFilters();
      refreshItems().catch(showError);
    });
    refs.tagSearch.addEventListener("change", () => {
      state.segmentQuery = refs.tagSearch.value.trim();
      refreshItems().catch(showError);
    });
    refs.tagSearch.addEventListener("keyup", (event) => {
      if (event.key === "Enter") {
        state.segmentQuery = refs.tagSearch.value.trim();
        refreshItems().catch(showError);
      }
    });

    refs.viewModeGroup.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-mode]");
      if (!button) return;
      state.viewMode = button.dataset.mode;
      saveStored(STORAGE_KEYS.viewMode, state.viewMode);
      renderViewer();
    });

    document.addEventListener("keydown", (event) => {
      if (shouldIgnoreListArrowNavigation(event.target)) return;
      if (!state.items.length) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        selectRelativeItem(1).catch(showError);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        selectRelativeItem(-1).catch(showError);
      }
    });

    document.addEventListener("click", (event) => {
      if (state.apiModelMenuOpen && !event.target.closest("#apiModelPicker")) {
        closeApiModelMenu();
      }
      if (state.ollamaModelMenuOpen && !event.target.closest("#ollamaModelPicker")) {
        closeOllamaModelMenu();
      }
    });

    refs.addTagBtn.addEventListener("click", () => {
      const segments = splitSegmentInput(refs.newTagInput.value);
      if (!segments.length) return;
      appendSegmentsToCaption(segments);
      refs.newTagInput.value = "";
    });
    refs.quickTagToggleBtn.addEventListener("click", () => toggleQuickTags());
    refs.quickTagSaveBtn.addEventListener("click", saveQuickTags);
    refs.captionEditor?.addEventListener("input", () => {
      state.currentText = refs.captionEditor.value;
      syncSegmentsFromText();
      syncCaptionDirty();
      renderTags();
    });
    refs.newTagInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        refs.addTagBtn.click();
      }
    });

    document.querySelectorAll(".template-row").forEach((row) => {
      const targetId = row.dataset.templateTarget;
      const select = row.querySelector(".promptTemplateSelect");
      row.querySelector(".applyTemplateBtn").addEventListener("click", () => {
        const template = templateById(select.value);
        const textarea = document.querySelector(`#${targetId}`);
        if (template && textarea) {
          textarea.value = template.content;
          textarea.dispatchEvent(new Event("change"));
        }
      });
      row.querySelector(".saveTemplateBtn").addEventListener("click", () => {
        savePromptTemplateFor(targetId).catch(showError);
      });
      row.querySelector(".deleteTemplateBtn").addEventListener("click", () => {
        const template = templateById(select.value);
        if (!template) return;
        if (!window.confirm(`确定删除模板「${template.name}」？`)) return;
        deletePromptTemplate(template.id).catch(showError);
      });
    });

    refs.saveTagsBtn.addEventListener("click", () => runWithStatus("正在保存 caption...", () => saveCurrentCaption()).catch(showError));
    refs.translateCurrentBtn.addEventListener("click", () => runWithStatus("正在翻译当前内容...", () => translateCurrent()).catch(showError));
    refs.batchAddBtn.addEventListener("click", () => runWithStatus("正在批量添加短语...", () => batchAdd()).catch(showError));
    refs.batchDeleteBtn.addEventListener("click", () => runWithStatus("正在批量删除短语...", () => batchDelete()).catch(showError));
    refs.batchReplaceBtn.addEventListener("click", () => runWithStatus("正在批量替换短语...", () => batchReplace()).catch(showError));
    refs.deleteCurrentBtn.addEventListener("click", () => runWithStatus("正在排除当前条目...", () => deleteCurrent()).catch(showError));
    refs.mergeWorkspaceBtn.addEventListener("click", () => runWithStatus("正在追加数据集...", () => mergeWorkspace()).catch(showError));
    refs.viewerScaleBtn.addEventListener("click", () => runWithStatus("正在缩放 Viewer 当前条目...", () => scaleViewerItem()).catch(showError));
    refs.viewerMatchResultBtn.addEventListener("click", () => runWithStatus("正在匹配 Viewer 控制图尺寸...", () => matchViewerControlsToResult()).catch(showError));
    refs.processImagesBtn.addEventListener("click", () => runWithStatus("正在处理图像工作集...", () => processImages()).catch(showError));
    refs.processMatchResultBtn?.addEventListener("click", () => runWithStatus("正在批量匹配结果尺寸...", () => processMatchResultSizes()).catch(showError));
    refs.exportDatasetBtn.addEventListener("click", () => runWithStatus("正在导出数据集...", () => exportDataset()).catch(showError));

    refs.installDepsBtn.addEventListener("click", () => runWithStatus("正在安装本地 Qwen 依赖...", () => installDeps()).catch(showError));
    refs.loadModelBtn.addEventListener("click", () => runWithStatus("正在加载本地模型...", () => loadModel()).catch(showError));
    refs.validateLocalBtn.addEventListener("click", () => runWithStatus("正在验证本地模型...", () => validateLocalModel()).catch(showError));
    refs.captionCurrentBtn.addEventListener("click", () => runWithStatus(`正在使用${activeCaptionBackendLabel()}标注当前图片...`, () => captionCurrentWithPayload(activeCaptionPayload())).catch(showError));
    refs.captionBatchBtn.addEventListener("click", () => runWithStatus(`正在使用${activeCaptionBackendLabel()}批量标注...`, () => startBatchCaptionWithPayload(activeCaptionPayload())).catch(showError));
    refs.stopBatchBtn.addEventListener("click", () => runWithStatus("正在停止当前任务...", () => stopBatchCaption()).catch(showError));

    refs.loadApiModelsBtn.addEventListener("click", () => runWithStatus("正在读取 API 模型列表...", () => loadApiModels()).catch(showError));
    refs.validateApiBtn.addEventListener("click", () => runWithStatus("正在验证 API 模型...", () => validateApiModel()).catch(showError));
    refs.loadOllamaModelsBtn.addEventListener("click", () => runWithStatus("正在读取 Ollama 模型列表...", () => loadOllamaModels()).catch(showError));
    refs.validateOllamaBtn.addEventListener("click", () => runWithStatus("正在验证 Ollama 模型...", () => validateOllamaModel()).catch(showError));

    document.addEventListener("visibilitychange", () => {
      pollAiStatus({ scheduleNext: true }).catch((error) => console.warn(error));
    });
  }

  async function bootstrap() {
    restorePersistedSettings();
    bindEvents();
    bindSettingsPersistence();
    setUtilityPanel(state.utilityPanel, { open: false, persist: false });
    updateControlFieldVisibility();
    renderWorkspaceBrowser();
    renderFilters();
    renderWorkspaceSummary();
    renderViewer();
    setCaptionEditorText("", { markSaved: true });
    renderTags();
    renderQuickTags();
    renderGlobalTags();
    refs.projectSortMode.value = state.projectSortMode;
    renderProjects();
    renderAiStatus();
    renderOverwriteModeHints();

    try {
      await loadAiOptions();
    } catch (error) {
      console.warn(error);
    }

    try {
      await loadPromptTemplates();
    } catch (error) {
      console.warn(error);
    }

    try {
      await refreshProjects();
    } catch (error) {
      console.warn(error);
    }

    try {
      const data = await apiGet("/api/workspace");
      applyWorkspaceSummary(data.workspace);
      if (!restoreCurrentProjectFromLastWorkspace(data.workspace)) inferSingleProjectForCurrentWorkspace();
      if (state.workspace?.counts?.all) {
        await refreshItems();
      }
    } catch (error) {
      console.warn(error);
    }

    if (!state.workspace?.counts?.all) {
      try {
        await openLastWorkspaceOnStartup();
      } catch (error) {
        console.warn(error);
        setAiStatusLine(`打开上次加载的数据目录失败：${error.message || error}`);
      }
    }

    await pollAiStatus();
    scheduleNextAiPoll(nextAiPollDelay(state.aiStatus));
  }

  return {
    restorePersistedSettings,
    bindSettingsPersistence,
    bindEvents,
    bootstrap,
  };
}
