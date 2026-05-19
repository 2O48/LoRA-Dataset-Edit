export function createBrowserModule({
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
  renderTags,
  renderGlobalTags,
  seedWorkspaceBrowserRootFromInputs,
  syncWorkspaceBrowserTargetVisibility,
  renderWorkspaceBrowser,
  closeUtilityPanel,
  setAiStatusLine,
}) {
  function currentIssueCount() {
    const stats = state.itemStats;
    if (!stats) return 0;
    return (
      Number(stats.no_control1 || 0) +
      Number(stats.no_control2 || 0) +
      Number(stats.no_control3 || 0) +
      Number(stats.no_result || 0) +
      Number(stats.no_txt || 0) +
      Number(stats.resolution_mismatch || 0)
    );
  }

  function imageUrl(role, name, thumb = false, width = 320, height = 220) {
    const url = new URL("/api/image", window.location.origin);
    url.searchParams.set("role", role);
    url.searchParams.set("name", name);
    if (thumb) {
      url.searchParams.set("thumb", "1");
      url.searchParams.set("width", String(width));
      url.searchParams.set("height", String(height));
    }
    return url.toString();
  }

  function activeControlCount() {
    const count = Number(refs.controlCount?.value || state.workspace?.settings?.control_count || 1);
    return Math.max(1, Math.min(3, count));
  }

  function activeControlRoles() {
    return ["control1", "control2", "control3"].slice(0, activeControlCount());
  }

  function renderWorkspaceSummary() {
    const counts = state.workspace?.counts;
    if (!counts) {
      refs.workspaceStat.textContent = "未加载工作区";
      refs.metricAll.textContent = "0";
      refs.metricTxt.textContent = "0";
      refs.metricIssues.textContent = "0";
      refs.metricFiltered.textContent = "0";
      return;
    }

    const editedText = counts.edited ? ` · 工作副本 ${counts.edited}` : "";
    const excludedText = counts.excluded ? ` · 已排除 ${counts.excluded}` : "";
    refs.workspaceStat.textContent = `共 ${counts.all} 项 · TXT ${counts.txt} · 分辨率异 ${counts.resolution_mismatch}${editedText}${excludedText}`;
    refs.metricAll.textContent = `${counts.all || 0}`;
    refs.metricTxt.textContent = `${counts.txt || 0}`;
    refs.metricIssues.textContent = `${currentIssueCount()}`;
    refs.metricFiltered.textContent = `${state.items.length || 0}`;
  }

  function renderFilterSummary() {
    const label = FILTER_LABELS[state.filter] || "筛选";
    const query = state.segmentQuery ? ` · 关键词: ${state.segmentQuery}` : "";
    refs.filterSummary.textContent = `${label}${query}`;
  }

  function renderFilters() {
    refs.filterGroup.querySelectorAll("button").forEach((button) => {
      button.classList.toggle("active", button.dataset.filter === state.filter);
    });
    renderFilterSummary();
  }

  function itemFlag(item) {
    const flags = [];
    if (!item.exists.result) flags.push(["缺结果", "danger"]);
    for (const role of activeControlRoles()) {
      if (!item.exists[role]) flags.push([`缺${ROLE_LABELS[role]}`, "warn"]);
    }
    if (!item.exists.txt) flags.push(["缺 TXT", "warn"]);
    if (item.flags.resolution_mismatch) flags.push(["分辨率异", "warn"]);
    if (!flags.length) flags.push(["正常", "ok"]);
    return flags;
  }

  function scrollSelectedItemIntoView(block = "center") {
    if (!state.selectedName) return;
    const activeCard = refs.itemList.querySelector(`.item-card[data-name="${CSS.escape(state.selectedName)}"]`);
    if (!activeCard) return;
    activeCard.scrollIntoView({ block, inline: "nearest" });
  }

  function updateViewerImageFit(img) {
    if (!img) return;
    const stage = img.closest(".image-stage");
    if (!stage || !img.naturalWidth || !img.naturalHeight) return;
    const stageStyle = window.getComputedStyle(stage);
    const horizontalPadding = parseFloat(stageStyle.paddingLeft || "0") + parseFloat(stageStyle.paddingRight || "0");
    const verticalPadding = parseFloat(stageStyle.paddingTop || "0") + parseFloat(stageStyle.paddingBottom || "0");
    const stageWidth = Math.max(0, stage.clientWidth - horizontalPadding);
    const stageHeight = Math.max(0, stage.clientHeight - verticalPadding);
    if (!stageWidth || !stageHeight) return;

    if (state.viewerImageMode === "actual") {
      img.style.width = `${img.naturalWidth}px`;
      img.style.height = `${img.naturalHeight}px`;
      return;
    }

    const scale = Math.min(stageWidth / img.naturalWidth, stageHeight / img.naturalHeight);
    img.style.width = `${Math.max(1, Math.floor(img.naturalWidth * scale))}px`;
    img.style.height = `${Math.max(1, Math.floor(img.naturalHeight * scale))}px`;
  }

  function updateAllViewerImageFits() {
    refs.viewerGrid.querySelectorAll(".image-stage img").forEach(updateViewerImageFit);
  }

  function ensureViewerResizeObserver() {
    if (state.viewerResizeObserver || typeof ResizeObserver === "undefined") return;
    state.viewerResizeObserver = new ResizeObserver(() => updateAllViewerImageFits());
    state.viewerResizeObserver.observe(refs.viewerGrid);
  }

  function renderItemList() {
    refs.itemList.textContent = "";
    refs.listStats.textContent = `${state.items.length} 项`;
    renderWorkspaceSummary();

    for (const item of state.items) {
      const thumbRole =
        item.exists.result
          ? "result"
          : item.exists.control1
            ? "control1"
            : item.exists.control2
              ? "control2"
              : item.exists.control3
                ? "control3"
                : "";
      const card = document.createElement("article");
      card.className = `item-card${item.name === state.selectedName ? " active" : ""}`;
      card.dataset.name = item.name;
      if (thumbRole) {
        const img = document.createElement("img");
        img.className = "item-thumb";
        img.src = imageUrl(thumbRole, item.name, true, 192, 156);
        img.alt = "";
        card.appendChild(img);
      } else {
        const placeholder = document.createElement("div");
        placeholder.className = "item-thumb-empty";
        placeholder.textContent = "无预览";
        card.appendChild(placeholder);
      }

      const right = document.createElement("div");
      const title = document.createElement("div");
      title.className = "item-title";
      title.textContent = item.name;
      right.appendChild(title);

      const flags = document.createElement("div");
      flags.className = "item-flags";
      for (const [text, cls] of itemFlag(item)) {
        const flag = document.createElement("span");
        flag.className = `flag ${cls}`;
        flag.textContent = text;
        flags.appendChild(flag);
      }
      right.appendChild(flags);
      card.appendChild(right);
      card.addEventListener("click", () => selectItem(item.name));
      refs.itemList.appendChild(card);
    }

    scrollSelectedItemIntoView("nearest");
  }

  function renderSelectionSummary() {
    const item = state.currentItem;
    refs.focusStat.textContent = item ? `当前: ${item.name}` : "未选择条目";
    if (refs.overviewCurrentName) refs.overviewCurrentName.textContent = item ? item.name : "未选择图片";
    if (refs.overviewCurrentMeta) {
      refs.overviewCurrentMeta.textContent = item
        ? `TXT ${item.exists.txt ? "已存在" : "未创建"} · ${activeControlRoles()
            .map((role) => `${ROLE_LABELS[role]} ${item.exists[role] ? "有" : "无"}`)
            .join(" · ")} · 结果图 ${item.exists.result ? "有" : "无"}`
        : "加载工作区后，在浏览区选择条目开始编辑。";
    }
  }

  function renderViewer() {
    const item = state.currentItem;
    ensureViewerResizeObserver();
    refs.viewerGrid.dataset.mode = state.viewMode;
    refs.viewerGrid.dataset.imageMode = state.viewerImageMode || "fit";
    refs.currentName.textContent = item ? item.name : "未选择图片";
    refs.currentMeta.textContent = item
      ? `TXT: ${item.exists.txt ? "已存在" : "未创建"} · ${activeControlRoles()
          .map((role) => `${ROLE_LABELS[role]}: ${item.exists[role] ? "有" : "无"}`)
          .join(" · ")} · 结果图: ${item.exists.result ? "有" : "无"}`
      : "选择左侧条目开始浏览。";

    refs.viewModeGroup.querySelectorAll("button").forEach((button) => {
      button.classList.toggle("active", button.dataset.mode === state.viewMode);
    });

    const visibleRoles =
      state.viewMode === "one"
        ? ["result"]
        : state.viewMode === "two"
          ? ["control1", "result"]
          : state.viewMode === "three"
            ? ["control1", "control2", "result"]
            : ["control1", "control2", "control3", "result"];

    refs.viewerGrid.querySelectorAll(".image-card").forEach((card) => {
      const role = card.dataset.role;
      card.style.display = visibleRoles.includes(role) ? "flex" : "none";
      const stage = card.querySelector(".image-stage");
      const resLabel = card.querySelector(".res-label");
      if (!item || !item.exists[role]) {
        stage.textContent = "";
        const placeholder = document.createElement("div");
        placeholder.className = "placeholder";
        placeholder.textContent = `没有${ROLE_LABELS[role] || role}`;
        stage.appendChild(placeholder);
        resLabel.textContent = "";
        return;
      }
      stage.textContent = "";
      const img = document.createElement("img");
      img.src = imageUrl(role, item.name);
      img.alt = item.name;
      img.title = state.viewerImageMode === "actual" ? "点击切换为完整显示" : "点击切换为 100% 大小";
      img.addEventListener("load", () => updateViewerImageFit(img));
      img.addEventListener("click", () => {
        state.viewerImageMode = state.viewerImageMode === "actual" ? "fit" : "actual";
        renderViewer();
      });
      stage.appendChild(img);
      const size = item.resolution[role];
      resLabel.textContent = Array.isArray(size) ? `${size[0]}×${size[1]}` : "";
    });

    const canProcess = Boolean(item);
    if (refs.viewerScaleBtn) refs.viewerScaleBtn.disabled = !canProcess;
    if (refs.viewerMatchResultBtn) refs.viewerMatchResultBtn.disabled = !canProcess || !item.exists.result;

    if (!item) {
      refs.resolutionNote.textContent = "等待载入分辨率信息";
      renderSelectionSummary();
      return;
    }

    const resultRes = item.resolution.result;
    const comparisons = activeControlRoles()
      .map((role) => ({ role, size: item.resolution[role] }))
      .filter((row) => Array.isArray(row.size) && Array.isArray(resultRes));

    if (!Array.isArray(resultRes)) {
      refs.resolutionNote.textContent = "当前条目缺少结果图分辨率信息";
    } else if (!comparisons.length) {
      refs.resolutionNote.textContent = `结果图分辨率：${resultRes[0]}×${resultRes[1]} · 当前无可比对控制图`;
    } else {
      const mismatches = comparisons.filter(
        (row) => row.size[0] !== resultRes[0] || row.size[1] !== resultRes[1],
      );
      refs.resolutionNote.textContent = mismatches.length
        ? mismatches
            .map((row) => `${ROLE_LABELS[row.role]} ${row.size[0]}×${row.size[1]} 与结果图 ${resultRes[0]}×${resultRes[1]} 不一致`)
            .join(" · ")
        : `控制图与结果图分辨率一致：${resultRes[0]}×${resultRes[1]}`;
    }

    renderSelectionSummary();
    updateAllViewerImageFits();
  }

  function shouldIgnoreListArrowNavigation(target) {
    if (!(target instanceof Element)) return false;
    if (target.closest("input, textarea, select, button, a, .utility-page-shell, [contenteditable='true']")) return true;
    return false;
  }

  async function refreshItems(options = {}) {
    const { skipDirtyCheck = false, suppressSelectionSync = false } = options;
    const data = await apiGet("/api/items", { filter: state.filter, tag: state.segmentQuery });
    state.items = data.items;
    state.itemStats = data.stats;
    state.globalSegments = data.global_segments || data.global_tags || [];
    renderFilters();
    renderItemList();
    renderGlobalTags();
    renderWorkspaceSummary();

    if (!state.items.length) {
      state.selectedName = "";
      state.currentItem = null;
      setCaptionEditorText("", { markSaved: true });
      renderViewer();
      renderTags();
      return;
    }

    if (suppressSelectionSync) {
      return;
    }

    const stillExists = state.items.some((item) => item.name === state.selectedName);
    const nextName = stillExists ? state.selectedName : state.items[0].name;
    await selectItem(nextName, !stillExists, { skipDirtyCheck });
  }

  async function selectItem(name, rerenderList = true, options = {}) {
    const { skipDirtyCheck = false } = options;
    if (!skipDirtyCheck && name !== state.selectedName) {
      const ok = await confirmDiscardCaptionChanges();
      if (!ok) return;
    }
    state.selectedName = name;
    const data = await apiGet("/api/item", { name });
    state.currentItem = data.item;
    setCaptionEditorText(data.item.text || "", { markSaved: true });
    if (rerenderList) renderItemList();
    renderViewer();
    renderTags();
    scrollSelectedItemIntoView("nearest");
  }

  async function selectRelativeItem(offset) {
    if (!state.items.length) return;
    const currentIndex = state.items.findIndex((item) => item.name === state.selectedName);
    const baseIndex = currentIndex >= 0 ? currentIndex : 0;
    const nextIndex = Math.max(0, Math.min(state.items.length - 1, baseIndex + offset));
    const nextItem = state.items[nextIndex];
    if (!nextItem || nextItem.name === state.selectedName) {
      scrollSelectedItemIntoView("nearest");
      return;
    }
    await selectItem(nextItem.name);
    scrollSelectedItemIntoView("nearest");
  }

  function applyWorkspaceSummary(workspace) {
    state.workspace = workspace;
    const dirs = state.workspace?.dirs || {};
    const settings = state.workspace?.settings || {};
    refs.controlCount.value = String(settings.control_count || refs.controlCount.value || "1");
    refs.ignoreTokensInput.value = Array.isArray(settings.ignore_tokens)
      ? settings.ignore_tokens.join(", ")
      : refs.ignoreTokensInput.value;
    refs.control1Dir.value = dirs.control1 || "";
    refs.control2Dir.value = dirs.control2 || "";
    refs.control3Dir.value = dirs.control3 || "";
    refs.resultDir.value = dirs.result || "";
    seedWorkspaceBrowserRootFromInputs();
    updateControlFieldVisibility();
    renderWorkspaceBrowser();
    renderWorkspaceSummary();
  }

  function workspaceOpenPayloadFromInputs() {
    return {
      control1_dir: refs.control1Dir.value.trim(),
      control2_dir: refs.control2Dir.value.trim(),
      control3_dir: refs.control3Dir.value.trim(),
      result_dir: refs.resultDir.value.trim(),
      control_count: Number(refs.controlCount.value || 1),
      ignore_tokens: refs.ignoreTokensInput.value.trim(),
    };
  }

  function saveLastWorkspaceOpenPayload(payload) {
    const hasDirectory = ["control1_dir", "control2_dir", "control3_dir", "result_dir"].some((key) => payload[key]);
    if (!hasDirectory) return;
    saveStored(STORAGE_KEYS.lastWorkspaceDirs, JSON.stringify(payload));
  }

  async function loadWorkspace() {
    const payload = workspaceOpenPayloadFromInputs();
    const data = await apiPost("/api/workspace/open", payload);
    applyWorkspaceSummary(data.workspace);
    saveLastWorkspaceOpenPayload(payload);
    await refreshItems();
    closeUtilityPanel();
  }

  async function rescanWorkspace() {
    const data = await apiPost("/api/workspace/rescan", {});
    applyWorkspaceSummary(data.workspace);
    await refreshItems();
    setAiStatusLine("工作区已重扫。导入中的文件如果已落盘，现在会重新进入列表。");
  }

  async function mergeWorkspace() {
    const data = await apiPost("/api/workspace/merge", {
      control1_dir: refs.mergeControl1Dir.value.trim(),
      control2_dir: refs.mergeControl2Dir.value.trim(),
      control3_dir: refs.mergeControl3Dir.value.trim(),
      result_dir: refs.mergeResultDir.value.trim(),
      control_count: Number(refs.controlCount.value || 1),
    });
    applyWorkspaceSummary(data.workspace);
    await refreshItems({ skipDirtyCheck: true });
    refs.mergeStatus.textContent = `已追加 ${data.merged || 0} 项到当前工作区`;
    setAiStatusLine(`已追加数据集：${data.merged || 0} 项`);
  }

  function updateControlFieldVisibility() {
    const count = activeControlCount();
    const previousCount = Number(state.workspace?.settings?.control_count || refs.controlCount.dataset.previousCount || 1);
    document.querySelectorAll("[data-control-field]").forEach((node) => {
      const roleIndex = Number(node.getAttribute("data-control-field"));
      node.style.display = roleIndex <= count ? "" : "none";
    });
    document.querySelectorAll("[data-merge-control-field]").forEach((node) => {
      const roleIndex = Number(node.getAttribute("data-merge-control-field"));
      node.style.display = roleIndex <= count ? "" : "none";
    });

    refs.filterGroup.querySelectorAll("button[data-filter]").forEach((button) => {
      const filter = button.dataset.filter;
      const shouldHide =
        (filter === "no_control2" && count < 2) ||
        (filter === "no_control3" && count < 3);
      button.style.display = shouldHide ? "none" : "";
    });
    if ((state.filter === "no_control2" && count < 2) || (state.filter === "no_control3" && count < 3)) {
      state.filter = "all";
    }
    syncWorkspaceBrowserTargetVisibility();

    const allowedModes = count === 1 ? ["one", "two"] : count === 2 ? ["one", "two", "three"] : ["one", "two", "three", "four"];
    refs.viewModeGroup.querySelectorAll("button[data-mode]").forEach((button) => {
      button.style.display = allowedModes.includes(button.dataset.mode) ? "" : "none";
    });
    if (count > previousCount) {
      state.viewMode = allowedModes.at(-1) || "two";
      saveStored(STORAGE_KEYS.viewMode, state.viewMode);
    } else if (!allowedModes.includes(state.viewMode)) {
      state.viewMode = allowedModes.at(-1) || "two";
      saveStored(STORAGE_KEYS.viewMode, state.viewMode);
    }
    refs.controlCount.dataset.previousCount = String(count);
    renderFilters();
    if (state.currentItem) {
      renderViewer();
    }
  }

  return {
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
  };
}
