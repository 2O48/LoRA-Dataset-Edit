export function createCaptionModule({
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
}) {
  function localModels() {
    return Array.isArray(state.aiOptions.local_models) ? state.aiOptions.local_models : [];
  }

  function currentLocalModel() {
    return localModels().find((item) => item.key === refs.aiModel.value) || null;
  }

  function buildLocalModelMetaTitle(model) {
    const lines = [
      `模型仓库: ${model.repo_id}`,
      `默认目录: ${model.model_dir_rel || model.model_dir || model.label}`,
    ];
    if (model.project_local_available) {
      lines.push("当前状态: 项目目录中已存在完整模型");
    } else {
      lines.push("当前状态: 首次加载会下载到项目内 models 目录");
    }
    if (model.legacy_comfyui_dir) {
      lines.push(`兼容旧目录: ${model.legacy_comfyui_dir}`);
    }
    if (model.legacy_hf_cache_available) {
      lines.push("兼容旧缓存: models/huggingface");
    }
    return lines.join("\n");
  }

  function renderLocalModelMeta() {
    const model = currentLocalModel();
    if (!model) {
      refs.localModelMeta.textContent = "选择模型后可直接加载或验证，验证会做一次真实推理试跑。";
      refs.localModelMeta.removeAttribute("title");
      return;
    }
    let sourceNote = `首次加载会下载到 ${model.model_dir_rel || model.label}`;
    if (model.project_local_available) {
      sourceNote = `项目内已就绪：${model.model_dir_rel || model.label}`;
    } else if (model.legacy_comfyui_dir) {
      sourceNote = "检测到旧 ComfyUI 目录，可直接复用";
    } else if (model.legacy_hf_cache_available) {
      sourceNote = "检测到旧缓存，可直接复用";
    }
    refs.localModelMeta.textContent = `${model.label} · ${model.size_note} · ${sourceNote}`;
    refs.localModelMeta.title = buildLocalModelMetaTitle(model);
  }

  function renderOverwriteModeHints() {
    const rows = [
      {
        select: refs.overwriteMode,
        label: refs.localPromptLabel,
        hint: refs.localPromptModeHint,
        defaultLabel: "Prompt",
        defaultHint: "启动标注请使用顶部命令栏；这里仅调整本地模型参数。",
      },
      {
        select: refs.apiOverwriteMode,
        label: refs.apiPromptLabel,
        hint: refs.apiPromptModeHint,
        defaultLabel: "API Prompt",
        defaultHint: "选择顶部“OpenAI 兼容 API”后，标注按钮会自动使用这组配置。",
      },
      {
        select: refs.ollamaOverwriteMode,
        label: refs.ollamaPromptLabel,
        hint: refs.ollamaPromptModeHint,
        defaultLabel: "Ollama Prompt",
        defaultHint: "选择顶部“Ollama”后，标注按钮会自动使用这组配置。",
      },
    ];

    rows.forEach((row) => {
      if (!row.select || !row.label || !row.hint) return;
      const isModify = row.select.value === "modify";
      row.label.textContent = isModify ? "修改指令" : row.defaultLabel;
      row.hint.textContent = isModify
        ? "修改模式会把已有 TXT 与这里的修改指令一起发给模型，返回修改后的完整 caption；如果当前没有 TXT，则退化为覆盖生成。"
        : row.defaultHint;
    });
  }

  function renderLocalModelOptions() {
    const models = localModels();
    const fallbackModel = state.aiOptions.default_local_model || "qwen3.5-4b";
    const storedModel = readStored(STORAGE_KEYS.localModel, fallbackModel);
    const nextValue = models.some((item) => item.key === refs.aiModel.value)
      ? refs.aiModel.value
      : models.some((item) => item.key === storedModel)
        ? storedModel
        : fallbackModel;

    refs.aiModel.innerHTML = models
      .map((item) => `<option value="${item.key}">${item.label} · ${item.size_note}</option>`)
      .join("");
    refs.aiModel.value = nextValue;
    renderLocalModelMeta();
  }

  function renderOllamaSuggestions() {
    if (!refs.ollamaModelList) return;
    const query = state.ollamaModelQuery || "";
    const currentValue = refs.ollamaModelName.value.trim();
    const models = state.ollamaModels.filter((name) => modelMatchesQuery(name, query));
    refs.ollamaModelList.textContent = "";

    if (currentValue && modelMatchesQuery(currentValue, query) && !models.includes(currentValue)) {
      const customButton = document.createElement("button");
      customButton.type = "button";
      customButton.className = "model-picker-option custom";
      customButton.textContent = `使用当前输入：${currentValue}`;
      customButton.addEventListener("click", () => selectOllamaModel(currentValue));
      refs.ollamaModelList.appendChild(customButton);
    }

    if (!models.length) {
      const empty = document.createElement("div");
      empty.className = "model-picker-empty";
      empty.textContent = state.ollamaModels.length ? "没有匹配的模型" : "读取模型后可在这里选择";
      refs.ollamaModelList.appendChild(empty);
      return;
    }

    for (const name of models) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "model-picker-option";
      button.classList.toggle("active", name === currentValue);
      button.textContent = name;
      button.addEventListener("click", () => selectOllamaModel(name));
      refs.ollamaModelList.appendChild(button);
    }
  }

  function modelMatchesQuery(name, query) {
    return !query || name.toLowerCase().includes(query.toLowerCase());
  }

  function closeApiModelMenu() {
    if (!refs.apiModelMenu) return;
    state.apiModelMenuOpen = false;
    refs.apiModelMenu.hidden = true;
    refs.apiModelMenuBtn?.setAttribute("aria-expanded", "false");
  }

  function selectApiModel(name) {
    refs.apiModelName.value = name;
    saveStored(STORAGE_KEYS.apiModelName, name);
    closeApiModelMenu();
  }

  function closeOllamaModelMenu() {
    if (!refs.ollamaModelMenu) return;
    state.ollamaModelMenuOpen = false;
    refs.ollamaModelMenu.hidden = true;
    refs.ollamaModelMenuBtn?.setAttribute("aria-expanded", "false");
  }

  function selectOllamaModel(name) {
    refs.ollamaModelName.value = name;
    saveStored(STORAGE_KEYS.ollamaModelName, name);
    closeOllamaModelMenu();
  }

  function renderApiModelSuggestions() {
    if (!refs.apiModelList) return;
    const query = state.apiModelQuery || "";
    const currentValue = refs.apiModelName.value.trim();
    const models = state.apiModels.filter((name) => modelMatchesQuery(name, query));
    refs.apiModelList.textContent = "";

    if (currentValue && modelMatchesQuery(currentValue, query) && !models.includes(currentValue)) {
      const customButton = document.createElement("button");
      customButton.type = "button";
      customButton.className = "model-picker-option custom";
      customButton.textContent = `使用当前输入：${currentValue}`;
      customButton.addEventListener("click", () => selectApiModel(currentValue));
      refs.apiModelList.appendChild(customButton);
    }

    if (!models.length) {
      const empty = document.createElement("div");
      empty.className = "model-picker-empty";
      empty.textContent = state.apiModels.length ? "没有匹配的模型" : "刷新模型后可在这里选择";
      refs.apiModelList.appendChild(empty);
      return;
    }

    for (const name of models) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "model-picker-option";
      button.classList.toggle("active", name === currentValue);
      button.textContent = name;
      button.addEventListener("click", () => selectApiModel(name));
      refs.apiModelList.appendChild(button);
    }
  }

  function openApiModelMenu({ focusSearch = true } = {}) {
    if (!refs.apiModelMenu) return;
    state.apiModelMenuOpen = true;
    refs.apiModelMenu.hidden = false;
    refs.apiModelMenuBtn?.setAttribute("aria-expanded", "true");
    state.apiModelQuery = "";
    refs.apiModelSearch.value = "";
    renderApiModelSuggestions();
    if (focusSearch) refs.apiModelSearch.focus();
  }

  function openOllamaModelMenu({ focusSearch = true } = {}) {
    if (!refs.ollamaModelMenu) return;
    state.ollamaModelMenuOpen = true;
    refs.ollamaModelMenu.hidden = false;
    refs.ollamaModelMenuBtn?.setAttribute("aria-expanded", "true");
    state.ollamaModelQuery = "";
    refs.ollamaModelSearch.value = "";
    renderOllamaSuggestions();
    if (focusSearch) refs.ollamaModelSearch.focus();
  }

  function summarizeRemoteService(service, idleLabel) {
    if (service.last_model) {
      return `${service.status} · ${service.last_model}`;
    }
    if (service.status === "error") {
      return "错误";
    }
    return idleLabel;
  }

  function setOptionalText(ref, value) {
    if (ref) ref.textContent = value;
  }

  function renderAiStatus() {
    const ai = state.aiStatus;
    if (!ai) {
      refs.aiStat.textContent = `AI 待命 · ${activeCaptionBackendLabel()}`;
      setOptionalText(refs.localAiSummary, "未启动");
      setOptionalText(refs.apiAiSummary, "未配置");
      setOptionalText(refs.ollamaAiSummary, "未配置");
      setOptionalText(refs.localAiStatusText, "待命");
      setOptionalText(refs.apiAiStatusText, "待命");
      setOptionalText(refs.ollamaAiStatusText, "待命");
      setAiStatusLine("等待启动服务");
      refs.aiProgressBar.style.width = "0%";
      renderImageProcessStatus(null);
      return;
    }

    const localSummary = ai.service.ready
      ? `已就绪 · ${ai.service.loaded_models.join(", ") || "未加载模型"}`
      : ai.service.running
        ? `${ai.service.status} · ${ai.service.progress_msg || "处理中"}`
        : "未启动";
    const apiSummary = summarizeRemoteService(ai.api_service, "未配置");
    const ollamaSummary = summarizeRemoteService(ai.ollama_service, "未配置");

    setOptionalText(refs.localAiSummary, localSummary);
    setOptionalText(refs.apiAiSummary, apiSummary);
    setOptionalText(refs.ollamaAiSummary, ollamaSummary);
    setOptionalText(refs.localAiStatusText, localSummary);
    setOptionalText(refs.apiAiStatusText, apiSummary);
    setOptionalText(refs.ollamaAiStatusText, ollamaSummary);

    renderImageProcessStatus(ai.image_process);

    if (ai.image_process?.running) {
      const modeLabel = ai.image_process.mode === "match_result" ? "匹配结果尺寸" : "图像处理";
      refs.aiStat.textContent = `${modeLabel} ${ai.image_process.done}/${ai.image_process.total}`;
    } else if (ai.batch.running) {
      const backendLabel =
        ai.batch.backend === "api" ? "API 批量" : ai.batch.backend === "ollama" ? "Ollama 批量" : "本地批量";
      refs.aiStat.textContent = `${backendLabel} ${ai.batch.done}/${ai.batch.total}`;
    } else if (ai.service.ready) {
      refs.aiStat.textContent = `本地就绪 · ${ai.service.loaded_models.join(", ") || "无模型"}`;
    } else if (ai.ollama_service.last_model) {
      refs.aiStat.textContent = `Ollama 最近使用 · ${ai.ollama_service.last_model}`;
    } else if (ai.api_service.last_model) {
      refs.aiStat.textContent = `API 最近使用 · ${ai.api_service.last_model}`;
    } else {
      refs.aiStat.textContent = `AI 待命 · ${activeCaptionBackendLabel()}`;
    }

    const statusLine = ai.image_process?.running
      ? `${ai.image_process.mode === "match_result" ? "匹配结果尺寸中" : "图像处理中"} ${ai.image_process.done}/${ai.image_process.total}${ai.image_process.current ? ` · ${ai.image_process.current}` : ""}`
      : ai.batch.running
        ? `${ai.batch.backend === "api" ? "API" : ai.batch.backend === "ollama" ? "Ollama" : "本地"}批量进行中 ${ai.batch.done}/${ai.batch.total}${ai.batch.current ? ` · ${ai.batch.current}` : ""}`
        : ai.installer.running
          ? "正在安装本地 Qwen 依赖..."
          : ai.ollama_service.status === "requesting"
            ? ai.ollama_service.progress_msg || "Ollama 请求中..."
            : ai.api_service.status === "requesting"
              ? ai.api_service.progress_msg || "API 请求中..."
              : ai.service.running
                ? `${ai.service.status} · ${ai.service.progress_msg || "待命"}`
                : "待命";
    setAiStatusLine(statusLine);

    const progress = ai.image_process?.running
      ? ai.image_process.progress_pct || 0
      : ai.batch.running
        ? (ai.batch.total ? (ai.batch.done / ai.batch.total) * 100 : 0)
        : ai.installer.running
          ? Math.max(ai.installer.progress_pct || 0, 8)
          : ai.api_service.status === "requesting" || ai.ollama_service.status === "requesting"
            ? 45
            : ["captioning", "loading", "starting", "busy"].includes(ai.service.status)
              ? Math.max(ai.service.progress_pct || 0, 20)
              : ai.service.progress_pct || 0;
    refs.aiProgressBar.style.width = `${Math.max(0, Math.min(progress, 100))}%`;

  }

  function localCaptionPayload() {
    return {
      backend: "local",
      model: refs.aiModel.value,
      overwrite_mode: refs.overwriteMode.value,
      mode: refs.captionMode.value,
      prompt: refs.customPrompt.value,
      max_tokens: Number(refs.maxTokens.value || 512),
      thinking: false,
    };
  }

  function apiCaptionPayload() {
    return {
      backend: "api",
      model: refs.apiModelName.value.trim(),
      api_base_url: refs.apiBaseUrl.value.trim(),
      api_key: refs.apiKey.value.trim(),
      overwrite_mode: refs.apiOverwriteMode.value,
      mode: refs.apiCaptionMode.value,
      prompt: refs.apiPrompt.value,
      max_tokens: Number(refs.apiMaxTokens.value || 512),
    };
  }

  function ollamaCaptionPayload() {
    return {
      backend: "ollama",
      model: refs.ollamaModelName.value.trim(),
      ollama_base_url: refs.ollamaBaseUrl.value.trim() || DEFAULT_OLLAMA_URL,
      overwrite_mode: refs.ollamaOverwriteMode.value,
      mode: refs.ollamaCaptionMode.value,
      prompt: refs.ollamaPrompt.value,
      max_tokens: Number(refs.ollamaMaxTokens.value || 512),
    };
  }

  async function loadModel() {
    await apiPost("/api/ai/load", { model: refs.aiModel.value });
    await pollAiStatus();
  }

  async function validateBackend(payload, successPrefix) {
    const data = await apiPost("/api/ai/validate", payload);
    const resultText = `${successPrefix}验证成功 · ${data.validation.model}${data.validation.result ? ` · ${data.validation.result}` : ""}`;
    setAiStatusLine(resultText);
    await pollAiStatus();
    return data;
  }

  async function validateLocalModel() {
    await validateBackend(
      {
        ...localCaptionPayload(),
        max_tokens: Math.min(Number(refs.maxTokens.value || 128), 128),
      },
      "本地模型",
    );
  }

  async function validateApiModel() {
    await validateBackend(
      {
        ...apiCaptionPayload(),
        max_tokens: Math.min(Number(refs.apiMaxTokens.value || 128), 128),
      },
      "API",
    );
  }

  async function validateOllamaModel() {
    await validateBackend(
      {
        ...ollamaCaptionPayload(),
        max_tokens: Math.min(Number(refs.ollamaMaxTokens.value || 128), 128),
      },
      "Ollama",
    );
  }

  async function loadApiModels() {
    const data = await apiPost("/api/api/models", {
      api_base_url: refs.apiBaseUrl.value.trim(),
      api_key: refs.apiKey.value.trim(),
    });
    state.apiModels = data.models || [];
    renderApiModelSuggestions();
    if (!refs.apiModelName.value.trim() && state.apiModels.length) {
      refs.apiModelName.value = state.apiModels[0];
      saveStored(STORAGE_KEYS.apiModelName, refs.apiModelName.value.trim());
    }
    if (state.apiModels.length) openApiModelMenu({ focusSearch: false });
    setAiStatusLine(state.apiModels.length ? `已读取 ${state.apiModels.length} 个 API 模型` : "API 未返回模型列表");
    await pollAiStatus();
  }

  async function loadOllamaModels() {
    const data = await apiGet("/api/ollama/models", {
      base_url: refs.ollamaBaseUrl.value.trim() || DEFAULT_OLLAMA_URL,
    });
    state.ollamaModels = data.models || [];
    renderOllamaSuggestions();
    if (!refs.ollamaModelName.value.trim() && state.ollamaModels.length) {
      refs.ollamaModelName.value = state.ollamaModels[0];
      saveStored(STORAGE_KEYS.ollamaModelName, refs.ollamaModelName.value.trim());
    }
    if (state.ollamaModels.length) openOllamaModelMenu({ focusSearch: false });
    setAiStatusLine(state.ollamaModels.length ? `已读取 ${state.ollamaModels.length} 个 Ollama 模型` : "Ollama 未返回模型列表");
  }

  async function captionCurrentWithPayload(payload) {
    if (!state.selectedName) return;
    scheduleNextAiPoll(500);
    await apiPost("/api/ai/caption", {
      name: state.selectedName,
      ...payload,
    });
    await pollAiStatus();
    await selectItem(state.selectedName, false);
    await refreshItems();
  }

  async function startBatchCaptionWithPayload(payload) {
    if (!state.items.length) return;
    await apiPost("/api/ai/batch/start", {
      names: visibleNames(),
      ...payload,
    });
    await pollAiStatus();
  }

  async function stopBatchCaption() {
    await apiPost("/api/ai/batch/stop", {});
    await pollAiStatus();
  }

  async function installDeps() {
    await apiPost("/api/ai/install", {});
    await pollAiStatus();
  }

  async function refreshCurrentItemIfVisible() {
    if (!state.selectedName) return;
    const stillVisible = state.items.some((item) => item.name === state.selectedName);
    if (!stillVisible) return;
    const data = await apiGet("/api/item", { name: state.selectedName });
    state.currentItem = data.item;
    if (!state.captionDirty) {
      setCaptionEditorText(data.item.text || "", { markSaved: true });
      renderTags();
    }
    renderViewer();
  }

  function hasActiveAiStatus(data) {
    return (
      data.image_process?.running ||
      data.batch.running ||
      data.installer.running ||
      ["busy", "loading", "captioning", "starting"].includes(data.service.status) ||
      data.api_service.status === "requesting" ||
      data.ollama_service.status === "requesting"
    );
  }

  function nextAiPollDelay(data = null) {
    if (document.hidden) return 15000;
    if (data && hasActiveAiStatus(data)) return 1500;
    return 6000;
  }

  function scheduleNextAiPoll(delay = 6000) {
    if (state.aiPollTimer) window.clearTimeout(state.aiPollTimer);
    state.aiPollTimer = window.setTimeout(() => {
      pollAiStatus({ scheduleNext: true }).catch((error) => console.warn(error));
    }, delay);
  }

  async function pollAiStatus({ scheduleNext = false } = {}) {
    if (state.aiPollInFlight) return;
    state.aiPollInFlight = true;
    let nextDelay = nextAiPollDelay();
    try {
      const data = await apiGet("/api/ai/status");
      state.aiStatus = data;
      renderAiStatus();
      nextDelay = nextAiPollDelay(data);

      const batchSignature = `${data.batch.running}-${data.batch.done}-${data.batch.total}-${data.batch.status}-${data.batch.backend}`;
      if (batchSignature !== state.lastBatchSignature) {
        state.lastBatchSignature = batchSignature;
        if (state.workspace?.counts?.all) {
          await refreshItems({
            skipDirtyCheck: true,
            suppressSelectionSync: state.captionDirty,
          });
        }
      }
      const process = data.image_process || {};
      const processSignature = `${process.running}-${process.done}-${process.total}-${process.status}-${process.mode || "process"}-${process.workspace_loaded}-${process.result?.path || ""}`;
      if (processSignature !== state.lastImageProcessSignature) {
        state.lastImageProcessSignature = processSignature;
        if (process.status === "done" && process.workspace_loaded && process.workspace) {
          applyWorkspaceSummary(process.workspace);
          await refreshItems({
            skipDirtyCheck: true,
            suppressSelectionSync: state.captionDirty,
          });
        }
      }
      if (hasActiveAiStatus(data)) {
        await refreshCurrentItemIfVisible();
      }
    } catch (error) {
      setAiStatusLine(error.message);
      nextDelay = document.hidden ? 15000 : 8000;
    } finally {
      state.aiPollInFlight = false;
      if (scheduleNext) scheduleNextAiPoll(nextDelay);
    }
  }

  async function loadAiOptions() {
    const data = await apiGet("/api/ai/options");
    state.aiOptions = data;
    renderLocalModelOptions();
    if (!refs.ollamaBaseUrl.value.trim()) {
      refs.ollamaBaseUrl.value = data.default_ollama_url || DEFAULT_OLLAMA_URL;
    }
  }

  function restoreCaptionSettings() {
    if (refs.captionBackend) {
      restoreSelectValue(refs.captionBackend, STORAGE_KEYS.captionBackend, "local");
    }
    refs.apiBaseUrl.value = readStored(STORAGE_KEYS.apiBaseUrl, "");
    refs.apiKey.value = readStored(STORAGE_KEYS.apiKey, "");
    refs.apiModelName.value = readStored(STORAGE_KEYS.apiModelName, "");
    refs.apiOverwriteMode.value = readStored(STORAGE_KEYS.apiOverwriteMode, refs.apiOverwriteMode.value);
    refs.apiCaptionMode.value = readStored(STORAGE_KEYS.apiCaptionMode, refs.apiCaptionMode.value);
    refs.apiMaxTokens.value = readStored(STORAGE_KEYS.apiMaxTokens, refs.apiMaxTokens.value);
    refs.apiPrompt.value = readStored(STORAGE_KEYS.apiPrompt, refs.apiPrompt.value);

    refs.ollamaBaseUrl.value = readStored(STORAGE_KEYS.ollamaBaseUrl, DEFAULT_OLLAMA_URL);
    refs.ollamaModelName.value = readStored(STORAGE_KEYS.ollamaModelName, "");
    refs.ollamaOverwriteMode.value = readStored(STORAGE_KEYS.ollamaOverwriteMode, refs.ollamaOverwriteMode.value);
    refs.ollamaCaptionMode.value = readStored(STORAGE_KEYS.ollamaCaptionMode, refs.ollamaCaptionMode.value);
    refs.ollamaMaxTokens.value = readStored(STORAGE_KEYS.ollamaMaxTokens, refs.ollamaMaxTokens.value);
    refs.ollamaPrompt.value = readStored(STORAGE_KEYS.ollamaPrompt, refs.ollamaPrompt.value);
  }

  return {
    renderLocalModelMeta,
    renderOverwriteModeHints,
    renderLocalModelOptions,
    renderOllamaSuggestions,
    selectApiModel,
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
  };
}
