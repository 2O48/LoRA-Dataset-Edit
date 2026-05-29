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
  applyProjectUiState,
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
}) {
  function enhanceSelectMenus() {
    const viewportPadding = 8;
    const menuGap = 6;

    const positionMenu = (shell, button, menu) => {
      const rect = button.getBoundingClientRect();
      const maxMenuHeight = Math.min(260, Math.floor(window.innerHeight * 0.45));
      const width = Math.min(rect.width, window.innerWidth - (viewportPadding * 2));
      const left = Math.min(Math.max(viewportPadding, rect.left), window.innerWidth - width - viewportPadding);
      const spaceBelow = window.innerHeight - rect.bottom - menuGap - viewportPadding;
      const spaceAbove = rect.top - menuGap - viewportPadding;
      const expectedHeight = Math.min(menu.scrollHeight || maxMenuHeight, maxMenuHeight);
      const opensUp = spaceBelow < expectedHeight && spaceAbove > spaceBelow;
      const availableHeight = Math.max(72, opensUp ? spaceAbove : spaceBelow);
      const menuHeight = Math.min(expectedHeight, availableHeight);

      shell.classList.toggle("drop-up", opensUp);
      menu.style.width = `${Math.round(width)}px`;
      menu.style.left = `${Math.round(left)}px`;
      menu.style.maxHeight = `${Math.round(Math.min(maxMenuHeight, availableHeight))}px`;
      menu.style.top = opensUp
        ? `${Math.round(Math.max(viewportPadding, rect.top - menuGap - menuHeight))}px`
        : `${Math.round(rect.bottom + menuGap)}px`;
      menu.classList.toggle("drop-up", opensUp);
    };

    const openMenu = (shell, button, menu) => {
      window.clearTimeout(menu.closeTimer);
      menu.classList.remove("menu-open", "menu-closing");
      menu.hidden = false;
      positionMenu(shell, button, menu);
      window.requestAnimationFrame(() => {
        menu.classList.add("menu-open");
      });
    };

    const closeMenu = (shell) => {
      const menu = shell.customSelectMenu;
      if (!menu || menu.hidden) return;
      window.clearTimeout(menu.closeTimer);
      shell.classList.remove("open");
      shell.querySelector(".custom-select-button")?.setAttribute("aria-expanded", "false");
      menu.classList.remove("menu-open");
      menu.classList.add("menu-closing");
      menu.closeTimer = window.setTimeout(() => {
        menu.hidden = true;
        menu.classList.remove("menu-closing", "drop-up");
      }, 230);
    };

    const closeMenus = (except = null) => {
      document.querySelectorAll(".custom-select.open").forEach((node) => {
        if (node === except) return;
        closeMenu(node);
      });
    };

    if (!enhanceSelectMenus.bound) {
      document.addEventListener("click", (event) => {
        if (event.target.closest(".custom-select, .custom-select-menu")) return;
        closeMenus();
      });
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeMenus();
      });
      window.addEventListener("resize", () => closeMenus());
      document.addEventListener("scroll", () => closeMenus(), true);
      enhanceSelectMenus.bound = true;
    }

    document.querySelectorAll("select").forEach((select) => {
      if (select.dataset.customSelectReady === "true") return;
      select.dataset.customSelectReady = "true";
      select.classList.add("native-select-hidden");

      const shell = document.createElement("div");
      shell.className = "custom-select";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "custom-select-button";
      button.setAttribute("aria-haspopup", "listbox");
      button.setAttribute("aria-expanded", "false");
      const label = document.createElement("span");
      label.className = "custom-select-label";
      const arrow = document.createElement("span");
      arrow.className = "custom-select-arrow";
      button.append(label, arrow);

      const menu = document.createElement("div");
      menu.className = "custom-select-menu select-menu-portal";
      menu.setAttribute("role", "listbox");
      menu.hidden = true;
      shell.customSelectMenu = menu;
      shell.append(button);
      select.insertAdjacentElement("afterend", shell);
      document.body.appendChild(menu);

      const sync = () => {
        const selected = select.selectedOptions?.[0] || select.options?.[select.selectedIndex] || select.options?.[0];
        label.textContent = selected?.textContent?.trim() || "选择";
        button.disabled = select.disabled;
        button.setAttribute("aria-label", select.getAttribute("aria-label") || label.textContent);
        menu.textContent = "";
        Array.from(select.options).forEach((option) => {
          const item = document.createElement("button");
          item.type = "button";
          item.className = "custom-select-option";
          item.textContent = option.textContent;
          item.disabled = option.disabled;
          item.setAttribute("role", "option");
          item.setAttribute("aria-selected", String(option.selected));
          if (option.selected) item.classList.add("selected");
          item.addEventListener("click", () => {
            if (option.disabled) return;
            select.value = option.value;
            select.dispatchEvent(new Event("change", { bubbles: true }));
            sync();
            closeMenus();
          });
          menu.appendChild(item);
        });
      };

      button.addEventListener("click", () => {
        const willOpen = !shell.classList.contains("open");
        closeMenus(shell);
        sync();
        shell.classList.toggle("open", willOpen);
        button.setAttribute("aria-expanded", String(willOpen));
        if (willOpen) {
          openMenu(shell, button, menu);
        } else {
          closeMenu(shell);
        }
      });
      select.addEventListener("change", sync);
      select.addEventListener("vds-select-sync", sync);
      new MutationObserver(sync).observe(select, { childList: true, subtree: true, attributes: true });
      sync();
    });
  }

  function restorePersistedSettings() {
    refs.controlCount.value = readStored(STORAGE_KEYS.controlCount, "1");
    refs.ignoreTokensInput.value = readStored(STORAGE_KEYS.ignoreTokens, "");
    if (refs.autoOpenLastWorkspace) {
      refs.autoOpenLastWorkspace.checked = readStored(STORAGE_KEYS.autoOpenLastWorkspace, "false") === "true";
    }
    refs.workspaceBrowserRoot.value = readStored(STORAGE_KEYS.workspaceBrowserRoot, "");
    state.browserRoot = refs.workspaceBrowserRoot.value.trim();
    restoreSelectValue(refs.exportTargetPixels, STORAGE_KEYS.exportTargetPixels, "4");
    restoreSelectValue(refs.exportSizeMultiple, STORAGE_KEYS.exportSizeMultiple, "16");
    refs.exportProjectName.value = readStored(STORAGE_KEYS.exportProjectName, "");
    refs.exportFormat.value = readStored(STORAGE_KEYS.exportFormat, refs.exportFormat.value);
    refs.exportOutputDir.value = readStored(STORAGE_KEYS.exportOutputDir, "");
    refs.exportProcessImages.checked = readStored(STORAGE_KEYS.exportProcessImages, "true") !== "false";
    refs.exportIncludeControls.checked = readStored(STORAGE_KEYS.exportIncludeControls, "true") !== "false";
    refs.exportPreserveSubfolders.checked = readStored(STORAGE_KEYS.exportPreserveSubfolders, "false") === "true";
    refs.viewerTargetPixels.value = readStored(STORAGE_KEYS.viewerTargetPixels, "4");
    refs.processProjectName.value = readStored(STORAGE_KEYS.processProjectName, "");
    refs.processIncludeControls.checked = readStored(STORAGE_KEYS.processIncludeControls, "true") !== "false";
    refs.processLoadWorkspace.checked = readStored(STORAGE_KEYS.processLoadWorkspace, "true") !== "false";
    refs.processOnlyMismatched.checked = readStored(STORAGE_KEYS.processOnlyMismatched, "true") !== "false";
    if (refs.swapControlDir) refs.swapControlDir.value = readStored(STORAGE_KEYS.swapControlDir, "");
    if (refs.swapResultDir) refs.swapResultDir.value = readStored(STORAGE_KEYS.swapResultDir, "");
    if (refs.swapSuffix) refs.swapSuffix.value = readStored(STORAGE_KEYS.swapSuffix, "_swap") || "_swap";
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
      state.browserRoot = refs.workspaceBrowserRoot.value.trim();
      saveStored(STORAGE_KEYS.workspaceBrowserRoot, state.browserRoot);
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
    refs.exportPreserveSubfolders.addEventListener("change", () => saveStored(STORAGE_KEYS.exportPreserveSubfolders, refs.exportPreserveSubfolders.checked ? "true" : "false"));
    refs.viewerTargetPixels.addEventListener("change", () => saveStored(STORAGE_KEYS.viewerTargetPixels, refs.viewerTargetPixels.value));
    refs.processProjectName.addEventListener("change", () => saveStored(STORAGE_KEYS.processProjectName, refs.processProjectName.value.trim()));
    refs.processIncludeControls.addEventListener("change", () => saveStored(STORAGE_KEYS.processIncludeControls, refs.processIncludeControls.checked ? "true" : "false"));
    refs.processLoadWorkspace.addEventListener("change", () => saveStored(STORAGE_KEYS.processLoadWorkspace, refs.processLoadWorkspace.checked ? "true" : "false"));
    refs.processOnlyMismatched.addEventListener("change", () => saveStored(STORAGE_KEYS.processOnlyMismatched, refs.processOnlyMismatched.checked ? "true" : "false"));
    refs.swapControlDir?.addEventListener("change", () => saveStored(STORAGE_KEYS.swapControlDir, refs.swapControlDir.value.trim()));
    refs.swapResultDir?.addEventListener("change", () => saveStored(STORAGE_KEYS.swapResultDir, refs.swapResultDir.value.trim()));
    refs.swapSuffix?.addEventListener("change", () => saveStored(STORAGE_KEYS.swapSuffix, refs.swapSuffix.value.trim() || "_swap"));

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
    enhanceSelectMenus();

    function numericCssVar(name, fallback) {
      const value = window.getComputedStyle(refs.workbenchShell).getPropertyValue(name).trim();
      const parsed = Number.parseFloat(value);
      return Number.isFinite(parsed) ? parsed : fallback;
    }

    function cssVarStorageKey(name) {
      return `vds-ui.${name.replace(/^--/, "")}`;
    }

    function legacyCssVarStorageKey(name) {
      return `lora-ui.${name.replace(/^--/, "")}`;
    }

    function setPanelWidthVar(name, value, min, max) {
      const clamped = Math.max(min, Math.min(max, value));
      refs.workbenchShell.style.setProperty(name, `${Math.round(clamped)}px`);
      window.localStorage.setItem(cssVarStorageKey(name), String(Math.round(clamped)));
    }

    function restorePanelWidthVar(name, fallback, min, max) {
      const stored = Number.parseFloat(
        window.localStorage.getItem(cssVarStorageKey(name)) || window.localStorage.getItem(legacyCssVarStorageKey(name)) || ""
      );
      if (Number.isFinite(stored)) setPanelWidthVar(name, stored, min, max);
      else refs.workbenchShell.style.setProperty(name, `${fallback}px`);
    }

    function bindPanelResizer(handle, { cssVar, fallback, min, max, direction }) {
      if (!handle) return;
      handle.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        const startX = event.clientX;
        const startWidth = numericCssVar(cssVar, fallback);
        refs.workbenchShell.classList.add("manual-resizing");
        handle.classList.add("dragging");
        handle.setPointerCapture?.(event.pointerId);
        const onMove = (moveEvent) => {
          const delta = (moveEvent.clientX - startX) * direction;
          setPanelWidthVar(cssVar, startWidth + delta, min, max);
        };
        const onUp = () => {
          handle.classList.remove("dragging");
          refs.workbenchShell.classList.remove("manual-resizing");
          document.removeEventListener("pointermove", onMove);
          document.removeEventListener("pointerup", onUp);
        };
        document.addEventListener("pointermove", onMove);
        document.addEventListener("pointerup", onUp, { once: true });
      });
    }

    function setContentSizeVar(name, value, min, max) {
      const clamped = Math.max(min, Math.min(max, value));
      refs.workbenchShell.style.setProperty(name, `${Math.round(clamped)}px`);
      window.localStorage.setItem(cssVarStorageKey(name), String(Math.round(clamped)));
    }

    function restoreContentSizeVar(name, fallback, min, max) {
      const stored = Number.parseFloat(
        window.localStorage.getItem(cssVarStorageKey(name)) || window.localStorage.getItem(legacyCssVarStorageKey(name)) || ""
      );
      if (Number.isFinite(stored)) setContentSizeVar(name, stored, min, max);
      else refs.workbenchShell.style.setProperty(name, `${fallback}px`);
    }

    function bindContentResizer(handle, { cssVar, axis, fallback, min, maxFor, direction = 1 }) {
      if (!handle) return;
      handle.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        const start = axis === "y" ? event.clientY : event.clientX;
        const startSize = numericCssVar(cssVar, fallback);
        const max = Math.max(min, Number(maxFor?.()) || fallback);
        refs.workbenchShell.classList.add("manual-resizing");
        handle.classList.add("dragging");
        handle.setPointerCapture?.(event.pointerId);
        const onMove = (moveEvent) => {
          const current = axis === "y" ? moveEvent.clientY : moveEvent.clientX;
          setContentSizeVar(cssVar, startSize + (current - start) * direction, min, max);
        };
        const onUp = () => {
          handle.classList.remove("dragging");
          refs.workbenchShell.classList.remove("manual-resizing");
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
    restoreContentSizeVar("--thumb-list-width", 320, 240, Math.max(320, (refs.workbenchLayout?.clientWidth || 980) - 460));
    restoreContentSizeVar("--viewer-panel-height", 520, 220, Math.max(320, (refs.workbenchLayout?.clientHeight || 820) - 220));
    restoreContentSizeVar("--caption-panel-width", 560, 280, Math.max(280, (refs.workbenchLayout?.clientWidth || 980) - 409));
    bindContentResizer(refs.listViewerResizer, {
      cssVar: "--thumb-list-width",
      axis: "x",
      fallback: 320,
      min: 240,
      maxFor: () => (refs.workbenchLayout?.clientWidth || window.innerWidth) - 460,
    });
    bindContentResizer(refs.viewerEditorResizer, {
      cssVar: "--viewer-panel-height",
      axis: "y",
      fallback: 520,
      min: 220,
      maxFor: () => (refs.workbenchLayout?.clientHeight || window.innerHeight) - 220,
    });
    bindContentResizer(refs.captionGlobalResizer, {
      cssVar: "--caption-panel-width",
      axis: "x",
      fallback: 560,
      min: 280,
      maxFor: () => refs.captionGlobalResizer?.parentElement?.clientWidth - 409,
    });

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
    const syncTagSearchClear = () => {
      if (refs.tagSearchClear) refs.tagSearchClear.hidden = !refs.tagSearch.value.trim();
    };
    const syncTagSearchMode = () => {
      state.listSearchMode = state.listSearchMode === "name" ? "name" : "phrase";
      state.listSearchMatchMode = state.listSearchMatchMode === "exact" ? "exact" : "contains";
      if (refs.tagSearch) {
        refs.tagSearch.placeholder = state.listSearchMode === "name"
          ? "搜索图片名称 / 子文件夹"
          : "搜索 caption 短语";
      }
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
    };
    let tagSearchDebounceTimer = 0;
    const clearTagSearchDebounce = () => {
      if (!tagSearchDebounceTimer) return;
      window.clearTimeout(tagSearchDebounceTimer);
      tagSearchDebounceTimer = 0;
    };
    const applyTagSearch = (options = {}) => {
      clearTagSearchDebounce();
      state.segmentQuery = refs.tagSearch.value.trim();
      syncTagSearchClear();
      refreshItems(options).catch(showError);
    };
    const scheduleTagSearch = () => {
      clearTagSearchDebounce();
      tagSearchDebounceTimer = window.setTimeout(() => {
        tagSearchDebounceTimer = 0;
        applyTagSearch({ skipDirtyCheck: true, suppressSelectionSync: true });
      }, 1000);
    };
    let tagSearchClearPointerHandled = false;
    const clearTagSearch = (event) => {
      event?.preventDefault();
      event?.stopPropagation();
      refs.tagSearch.value = "";
      refs.tagSearch.focus();
      applyTagSearch({ skipDirtyCheck: true, suppressSelectionSync: true });
    };
    syncTagSearchMode();
    syncTagSearchClear();
    refs.tagSearch.addEventListener("input", () => {
      syncTagSearchClear();
      scheduleTagSearch();
    });
    refs.tagSearch.addEventListener("change", () => {
      applyTagSearch();
    });
    refs.tagSearch.addEventListener("keyup", (event) => {
      syncTagSearchClear();
      if (event.key === "Enter") {
        applyTagSearch();
      }
    });
    refs.tagSearchClear?.addEventListener("pointerdown", (event) => {
      tagSearchClearPointerHandled = true;
      clearTagSearch(event);
    });
    refs.tagSearchClear?.addEventListener("click", (event) => {
      if (tagSearchClearPointerHandled) {
        tagSearchClearPointerHandled = false;
        event.preventDefault();
        event.stopPropagation();
        return;
      }
      clearTagSearch(event);
    });
    refs.tagSearchModeGroup?.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-search-mode]");
      if (!button) return;
      event.preventDefault();
      event.stopPropagation();
      const nextMode = button.dataset.searchMode === "name" ? "name" : "phrase";
      if (nextMode === state.listSearchMode) return;
      state.listSearchMode = nextMode;
      saveStored(STORAGE_KEYS.listSearchMode, state.listSearchMode);
      syncTagSearchMode();
      refreshItems({ skipDirtyCheck: true, suppressSelectionSync: true }).catch(showError);
    });
    refs.tagSearchMatchGroup?.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-search-match]");
      if (!button) return;
      event.preventDefault();
      event.stopPropagation();
      const nextMode = button.dataset.searchMatch === "exact" ? "exact" : "contains";
      if (nextMode === state.listSearchMatchMode) return;
      state.listSearchMatchMode = nextMode;
      saveStored(STORAGE_KEYS.listSearchMatchMode, state.listSearchMatchMode);
      syncTagSearchMode();
      refreshItems({ skipDirtyCheck: true, suppressSelectionSync: true }).catch(showError);
    });
    refs.listThumbModeSelect?.addEventListener("change", () => {
      state.listThumbMode = refs.listThumbModeSelect.value === "combined" ? "combined" : "result";
      saveStored(STORAGE_KEYS.listThumbMode, state.listThumbMode);
      renderFilters();
      renderViewer();
      refreshItems({ skipDirtyCheck: true, suppressSelectionSync: true }).catch(showError);
    });

    refs.viewModeGroup.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-mode]");
      if (!button) return;
      state.viewMode = button.dataset.mode;
      saveStored(STORAGE_KEYS.viewMode, state.viewMode);
      renderViewer();
    });

    document.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (!event.repeat) {
          runWithStatus("正在保存项目...", () => saveCurrentProject()).catch(showError);
        }
        return;
      }
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
      if (state.apiModelMenuOpen && !event.target.closest("#apiModelPicker, #apiModelMenu")) {
        closeApiModelMenu();
      }
      if (state.ollamaModelMenuOpen && !event.target.closest("#ollamaModelPicker, #ollamaModelMenu")) {
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
      const rawValue = refs.captionEditor.value;
      const normalized = normalizeCaptionInputText(rawValue);
      if (normalized !== rawValue) {
        const start = refs.captionEditor.selectionStart;
        const end = refs.captionEditor.selectionEnd;
        refs.captionEditor.value = normalized;
        refs.captionEditor.selectionStart = normalizeCaptionInputText(rawValue.slice(0, start)).length;
        refs.captionEditor.selectionEnd = normalizeCaptionInputText(rawValue.slice(0, end)).length;
      }
      state.currentText = normalized;
      syncSegmentsFromText();
      syncCaptionDirty();
      renderTags();
      scheduleCaptionAutosave?.();
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
      row.querySelector(".deleteTemplateBtn").addEventListener("click", async () => {
        const template = templateById(select.value);
        if (!template) return;
        if (!(await window.appConfirm(`确定删除模板「${template.name}」？`))) return;
        deletePromptTemplate(template.id).catch(showError);
      });
    });

    refs.translateCurrentBtn.addEventListener("click", () => runWithStatus("正在翻译当前内容...", () => translateCurrent()).catch(showError));
    refs.batchAddBeforeBtn?.addEventListener("click", () => runWithStatus("正在批量添加短语到最前...", () => batchAdd("before")).catch(showError));
    refs.batchAddAfterBtn?.addEventListener("click", () => runWithStatus("正在批量添加短语到最后...", () => batchAdd("after")).catch(showError));
    refs.batchDeleteBtn.addEventListener("click", () => runWithStatus("正在批量删除短语...", () => batchDelete()).catch(showError));
    refs.batchReplaceBtn.addEventListener("click", () => runWithStatus("正在批量替换短语...", () => batchReplace()).catch(showError));
    refs.batchRenameAddPrefixBtn?.addEventListener("click", () => runWithStatus("正在批量添加文件名前缀...", () => batchRename("add_prefix")).catch(showError));
    refs.batchRenameAddSuffixBtn?.addEventListener("click", () => runWithStatus("正在批量添加文件名后缀...", () => batchRename("add_suffix")).catch(showError));
    refs.batchRenameDeleteBtn?.addEventListener("click", () => runWithStatus("正在批量删除文件名文字...", () => batchRename("delete")).catch(showError));
    refs.batchRenameReplaceBtn?.addEventListener("click", () => runWithStatus("正在批量替换文件名文字...", () => batchRename("replace")).catch(showError));
    refs.swapPairsBtn?.addEventListener("click", () => runWithStatus("正在生成对调副本...", () => swapControlResultPairs()).catch(showError));
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
      if (state.currentProjectId && applyProjectUiState) {
        try {
          const detail = await apiGet("/api/projects/detail", { id: state.currentProjectId });
          applyProjectUiState(detail.workspace?.ui_state, detail.project?.name || state.currentProjectName);
        } catch (error) {
          console.warn(error);
        }
      }
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
