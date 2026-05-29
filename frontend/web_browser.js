export function createBrowserModule({
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
  renderTags,
  renderGlobalTags,
  seedWorkspaceBrowserRootFromInputs,
  syncWorkspaceBrowserTargetVisibility,
  resolveWorkspaceInputPath,
  workspacePathRelativeToBrowserRoot,
  renderWorkspaceBrowser,
  closeUtilityPanel,
  setAiStatusLine,
}) {
  const ITEM_DRAG_TYPE = "application/x-vds-item-name";
  const VIEWER_ROLE_DRAG_TYPE = "application/x-vds-viewer-role";
  const ITEM_CARD_SIZE_ANIMATION = {
    duration: 320,
    easing: "cubic-bezier(0.16, 1, 0.3, 1)",
  };
  const itemContextMenu = document.querySelector("#itemContextMenu");
  let itemContextTarget = null;
  let itemContextCloseTimer = 0;
  let itemThumbObserver = null;
  let imagePreview = null;

  function currentIssueCount() {
    return state.items.reduce((total, item) => {
      const hasMissingControl = activeControlRoles().some((role) => !item.exists?.[role]);
      const hasIssue = hasMissingControl || !item.exists?.result || !item.exists?.txt || Boolean(item.flags?.resolution_mismatch);
      return total + (hasIssue ? 1 : 0);
    }, 0);
  }

  function roleImageCount(role) {
    return state.items.reduce((total, item) => total + (item.exists?.[role] ? 1 : 0), 0);
  }

  function controlImageCount() {
    return activeControlRoles().reduce((total, role) => total + roleImageCount(role), 0);
  }

  function currentProjectLabel() {
    if (state.currentProjectName) return state.currentProjectName;
    if (state.workspace?.project_name) return state.workspace.project_name;
    return "未加载项目";
  }

  function imageUrl(role, name, thumb = false, width = 320, height = 220) {
    const url = new URL("/api/image", window.location.origin);
    url.searchParams.set("role", role);
    url.searchParams.set("name", name);
    url.searchParams.set("workspace", state.workspace?.workspace_key || String(state.workspaceImageVersion || 0));
    url.searchParams.set("refresh", String(state.imageRefreshToken || 0));
    if (thumb) {
      url.searchParams.set("thumb", "1");
      url.searchParams.set("width", String(width));
      url.searchParams.set("height", String(height));
    }
    return url.toString();
  }

  function disconnectItemThumbObserver() {
    itemThumbObserver?.disconnect();
    itemThumbObserver = null;
  }

  function ensureItemThumbObserver() {
    if (itemThumbObserver || typeof IntersectionObserver === "undefined") return itemThumbObserver;
    itemThumbObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            loadItemThumb(entry.target);
          } else {
            unloadItemThumb(entry.target);
          }
        }
      },
      { root: refs.itemList, rootMargin: "0px", threshold: 0.01 },
    );
    return itemThumbObserver;
  }

  function loadItemThumb(slot) {
    if (!slot || slot.dataset.loaded === "1") return;
    const src = slot.dataset.src;
    if (!src) return;
    slot.dataset.loaded = "1";
    const img = document.createElement("img");
    img.className = "item-thumb";
    img.src = src;
    img.alt = "";
    img.title = slot.title || "";
    img.loading = "lazy";
    img.decoding = "async";
    slot.replaceChildren(img);
    slot.classList.add("loaded");
  }

  function unloadItemThumb(slot) {
    if (!slot || slot.dataset.loaded !== "1") return;
    slot.dataset.loaded = "0";
    slot.replaceChildren();
    slot.classList.remove("loaded");
  }

  function createItemThumbSlot(item, role) {
    const slot = document.createElement("div");
    slot.className = "item-thumb-lazy";
    slot.dataset.src = imageUrl(role, item.name, true, 192, 156);
    slot.title = ROLE_LABELS[role] || role;
    const observer = ensureItemThumbObserver();
    if (observer) {
      observer.observe(slot);
    } else {
      loadItemThumb(slot);
    }
    return slot;
  }

  function activeControlCount() {
    const rawCount = refs.controlCount?.value ?? state.workspace?.settings?.control_count ?? 1;
    const count = Number(rawCount);
    return Math.max(0, Math.min(3, Number.isFinite(count) ? count : 1));
  }

  function activeControlRoles() {
    return ["control1", "control2", "control3"].slice(0, activeControlCount());
  }

  function renderWorkspaceSummary() {
    const counts = state.workspace?.counts;
    if (!counts) {
      refs.workspaceStat.textContent = "未加载项目";
      if (refs.metricAll) refs.metricAll.textContent = "0";
      if (refs.metricControlImages) refs.metricControlImages.textContent = "0";
      if (refs.metricResultImages) refs.metricResultImages.textContent = "0";
      refs.metricTxt.textContent = "0";
      if (refs.metricIssues) refs.metricIssues.textContent = "0";
      refs.metricFiltered.textContent = "0";
      return;
    }

    refs.workspaceStat.textContent = currentProjectLabel();
    if (refs.metricAll) refs.metricAll.textContent = `${counts.all || 0}`;
    if (refs.metricControlImages) refs.metricControlImages.textContent = `${controlImageCount()}`;
    if (refs.metricResultImages) refs.metricResultImages.textContent = `${roleImageCount("result")}`;
    refs.metricTxt.textContent = `${counts.txt || 0}`;
    if (refs.metricIssues) refs.metricIssues.textContent = `${currentIssueCount()}`;
    refs.metricFiltered.textContent = `${state.items.length || 0}`;
  }

  function renderFilterSummary() {
    if (!refs.listThumbModeSelect) return;
    const showCombined = activeControlCount() > 0 && controlImageCount() > 0;
    if (!showCombined && state.listThumbMode === "combined") {
      state.listThumbMode = "result";
      saveStored(STORAGE_KEYS.listThumbMode, state.listThumbMode);
    }
    const currentValue = state.listThumbMode === "combined" && showCombined ? "combined" : "result";
    refs.listThumbModeSelect.replaceChildren(
      new Option("仅结果图", "result"),
      ...(showCombined ? [new Option("控制图与结果图", "combined")] : []),
    );
    refs.listThumbModeSelect.value = currentValue;
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

  function displayItemName(name) {
    return `${name || ""}`.replace(/\\/g, "/");
  }

  function displayItemBasename(name) {
    const parts = displayItemName(name).split("/").filter(Boolean);
    return parts.length ? parts[parts.length - 1] : "";
  }

  function displayItemListName(name) {
    return state.itemFolderFilter ? displayItemBasename(name) : displayItemName(name);
  }

  function appendHighlightedText(parent, text, query) {
    const value = `${text ?? ""}`;
    const needle = `${query ?? ""}`.trim();
    if (!needle) {
      parent.textContent = value;
      return;
    }
    const lowerValue = value.toLowerCase();
    const lowerNeedle = needle.toLowerCase();
    let index = 0;
    let matchIndex = lowerValue.indexOf(lowerNeedle);
    if (matchIndex < 0) {
      parent.textContent = value;
      return;
    }
    parent.textContent = "";
    while (matchIndex >= 0) {
      if (matchIndex > index) {
        parent.appendChild(document.createTextNode(value.slice(index, matchIndex)));
      }
      const mark = document.createElement("span");
      mark.className = "search-hit";
      mark.textContent = value.slice(matchIndex, matchIndex + needle.length);
      parent.appendChild(mark);
      index = matchIndex + needle.length;
      matchIndex = lowerValue.indexOf(lowerNeedle, index);
    }
    if (index < value.length) {
      parent.appendChild(document.createTextNode(value.slice(index)));
    }
  }

  function itemFolder(name) {
    const parts = displayItemName(name).split("/").filter(Boolean);
    parts.pop();
    return parts.join("/");
  }

  function itemFolders() {
    return [...new Set(state.items.map((item) => itemFolder(item.name)).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" }));
  }

  function filteredItems() {
    const folder = state.itemFolderFilter || "";
    return folder ? state.items.filter((item) => itemFolder(item.name) === folder) : [...state.items];
  }

  function renderFolderFilters() {
    if (!refs.itemFolderFilters) return;
    const folders = itemFolders();
    if (state.itemFolderFilter && !folders.includes(state.itemFolderFilter)) {
      state.itemFolderFilter = "";
    }
    refs.itemFolderFilters.textContent = "";

    const allButton = document.createElement("button");
    allButton.type = "button";
    allButton.className = `folder-filter-chip all${state.itemFolderFilter ? "" : " active"}`;
    allButton.textContent = "全部";
    allButton.addEventListener("click", () => {
      state.itemFolderFilter = "";
      renderItemList();
      const next = state.visibleItems[0];
      if (next && !state.visibleItems.some((item) => item.name === state.selectedName)) {
        selectItem(next.name, false).catch(showError || console.error);
      }
    });
    refs.itemFolderFilters.appendChild(allButton);

    if (!folders.length) return;

    const group = document.createElement("div");
    group.className = "folder-filter-group";
    for (const folder of folders) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `folder-filter-chip${state.itemFolderFilter === folder ? " active" : ""}`;
      button.dataset.folder = folder;
      button.textContent = folder;
      button.addEventListener("click", () => {
        state.itemFolderFilter = folder;
        renderItemList();
        const next = state.visibleItems[0];
        if (next && !state.visibleItems.some((item) => item.name === state.selectedName)) {
          selectItem(next.name, false).catch(showError || console.error);
        }
      });
      button.addEventListener("dragover", (event) => {
        if (!Array.from(event.dataTransfer?.types || []).includes(ITEM_DRAG_TYPE)) return;
        event.preventDefault();
        button.classList.add("drag-over");
        event.dataTransfer.dropEffect = "move";
      });
      button.addEventListener("dragleave", () => {
        button.classList.remove("drag-over");
      });
      button.addEventListener("drop", (event) => {
        const name = event.dataTransfer?.getData(ITEM_DRAG_TYPE) || "";
        if (!name) return;
        event.preventDefault();
        button.classList.remove("drag-over");
        moveItemToFolder(name, folder).catch(showError || console.error);
      });
      group.appendChild(button);
    }
    refs.itemFolderFilters.appendChild(group);
  }

  async function moveItemToFolder(name, folder) {
    if (!name || !folder) return;
    if (itemFolder(name) === folder) return;
    if (!(await confirmDiscardCaptionChanges())) return;
    const data = await apiPost("/api/item/move-folder", { name, folder });
    if (data.workspace) applyWorkspaceSummary(data.workspace);
    state.itemFolderFilter = folder;
    setAiStatusLine(`已移动到子文件夹：${folder}`);
    await refreshItems({ skipDirtyCheck: true, suppressSelectionSync: true });
    await selectItem(data.new_name || name, true, { skipDirtyCheck: true });
  }

  function closeItemContextMenu() {
    if (!itemContextMenu) return;
    if (itemContextMenu.hidden) {
      itemContextTarget = null;
      return;
    }
    itemContextMenu.classList.remove("menu-open");
    itemContextMenu.classList.add("menu-closing");
    if (itemContextCloseTimer) window.clearTimeout(itemContextCloseTimer);
    itemContextCloseTimer = window.setTimeout(() => {
      itemContextCloseTimer = 0;
      itemContextMenu.hidden = true;
      itemContextMenu.classList.remove("menu-closing");
      itemContextTarget = null;
    }, 180);
  }

  function positionItemContextMenu(event) {
    if (!itemContextMenu) return;
    if (itemContextCloseTimer) {
      window.clearTimeout(itemContextCloseTimer);
      itemContextCloseTimer = 0;
    }
    itemContextMenu.classList.remove("menu-open", "menu-closing");
    itemContextMenu.hidden = false;
    const rect = itemContextMenu.getBoundingClientRect();
    const padding = 8;
    const left = Math.min(Math.max(padding, event.clientX), window.innerWidth - rect.width - padding);
    const top = Math.min(Math.max(padding, event.clientY), window.innerHeight - rect.height - padding);
    itemContextMenu.style.left = `${Math.round(left)}px`;
    itemContextMenu.style.top = `${Math.round(top)}px`;
    window.requestAnimationFrame(() => {
      itemContextMenu.classList.add("menu-open");
    });
  }

  function openItemContextMenu(event, item, title) {
    if (!itemContextMenu || !item?.name) return;
    event.preventDefault();
    event.stopPropagation();
    itemContextTarget = { item, title };
    positionItemContextMenu(event);
  }

  async function revealItemInFileManager(item) {
    if (!item?.name) return;
    const data = await apiPost("/api/item/reveal", { name: item.name });
    setAiStatusLine(`已在文件管理器中定位：${data.path || item.name}`);
  }

  async function cloneItemFiles(item) {
    if (!item?.name) return;
    if (item.name === state.selectedName && !(await confirmDiscardCaptionChanges())) return;
    const data = await apiPost("/api/item/clone", { name: item.name });
    if (data.workspace) applyWorkspaceSummary(data.workspace);
    setAiStatusLine(`已克隆：${displayItemName(item.name)} -> ${displayItemName(data.new_name || "")}`);
    await refreshItems({ skipDirtyCheck: true, suppressSelectionSync: true });
    await selectItem(data.new_name || item.name, true, { skipDirtyCheck: true });
  }

  async function trashItemFiles(item) {
    if (!item?.name) return;
    if (item.name === state.selectedName && !(await confirmDiscardCaptionChanges())) return;
    const ok = await window.appConfirm(`确定将「${displayItemName(item.name)}」的图像和关联 TXT 移到系统回收站吗？`, "删除图片");
    if (!ok) return;
    const data = await apiPost("/api/item/trash", { name: item.name });
    if (data.workspace) applyWorkspaceSummary(data.workspace);
    setAiStatusLine(`已移到系统回收站：${displayItemName(item.name)}`);
    await refreshItems({ skipDirtyCheck: true, suppressSelectionSync: true });
    const next = state.visibleItems[0];
    if (next) {
      await selectItem(next.name, true, { skipDirtyCheck: true });
    } else {
      state.selectedName = "";
      state.currentItem = null;
      setCaptionEditorText("", { markSaved: true });
      renderViewer();
      renderTags();
      renderGlobalTags();
      renderSelectionSummary();
    }
  }

  function ensureItemContextMenuEvents() {
    if (!itemContextMenu || state.itemContextMenuBound) return;
    state.itemContextMenuBound = true;
    itemContextMenu.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-action]");
      if (!button || !itemContextTarget) return;
      const { item, title } = itemContextTarget;
      closeItemContextMenu();
      const action = button.dataset.action;
      if (action === "rename") {
        beginInlineItemRename(item, title).catch(showError || console.error);
      } else if (action === "clone") {
        cloneItemFiles(item).catch(showError || console.error);
      } else if (action === "reveal") {
        revealItemInFileManager(item).catch(showError || console.error);
      } else if (action === "trash") {
        trashItemFiles(item).catch(showError || console.error);
      }
    });
    document.addEventListener("click", (event) => {
      if (event.target.closest("#itemContextMenu")) return;
      closeItemContextMenu();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeItemContextMenu();
    });
    window.addEventListener("resize", closeItemContextMenu);
    document.addEventListener("scroll", closeItemContextMenu, true);
  }

  function animateItemCardSize(card, mutate) {
    if (!card) {
      mutate();
      return;
    }
    const startHeight = card.getBoundingClientRect().height;
    card._sizeAnimation?.cancel();
    card._sizeAnimation = null;
    card.style.height = "";
    card.style.overflow = "";
    mutate();
    const endHeight = card.getBoundingClientRect().height;
    if (!Number.isFinite(startHeight) || !Number.isFinite(endHeight) || Math.abs(startHeight - endHeight) < 1) {
      return;
    }

    const cleanup = () => {
      if (card._sizeAnimation !== animation) return;
      card._sizeAnimation = null;
      card.style.height = "";
      card.style.overflow = "";
    };

    card.style.overflow = "hidden";
    card.style.height = `${endHeight}px`;
    const animation = card.animate(
      [{ height: `${startHeight}px` }, { height: `${endHeight}px` }],
      ITEM_CARD_SIZE_ANIMATION,
    );
    card._sizeAnimation = animation;
    animation.addEventListener("finish", cleanup, { once: true });
    animation.addEventListener("cancel", cleanup, { once: true });
  }

  async function beginInlineItemRename(item, title) {
    if (!item?.name) return;
    if (title?.querySelector(".item-rename-input")) {
      title.querySelector(".item-rename-input")?.focus();
      return;
    }
    if (!(await confirmDiscardCaptionChanges())) return;
    const currentBase = displayItemBasename(item.name);
    const originalText = displayItemListName(item.name);
    const input = document.createElement("textarea");
    input.className = "item-rename-input";
    input.value = currentBase;
    input.setAttribute("aria-label", "重命名图片名称");
    input.rows = 2;
    const card = title.closest(".item-card");
    animateItemCardSize(card, () => {
      title.textContent = "";
      title.appendChild(input);
      card?.classList.add("renaming");
    });
    input.focus();
    input.select();

    let committed = false;
    const restore = () => {
      animateItemCardSize(title.closest(".item-card"), () => {
        title.closest(".item-card")?.classList.remove("renaming");
        title.textContent = originalText;
      });
    };
    const commit = async () => {
      if (committed) return;
      const cleanBase = input.value.trim();
      if (!cleanBase || cleanBase === currentBase) {
        committed = true;
        restore();
        return;
      }
      if (cleanBase.includes("/") || cleanBase.includes("\\")) {
        setAiStatusLine("重命名只允许修改图片名称，不包含文件夹。");
        input.focus();
        input.select();
        return;
      }
      committed = true;
      input.disabled = true;
      try {
        const data = await apiPost("/api/item/rename", {
          name: item.name,
          new_name: cleanBase,
        });
        if (data.workspace) applyWorkspaceSummary(data.workspace);
        setAiStatusLine(`已重命名：${data.new_name || cleanBase}`);
        await refreshItems({ skipDirtyCheck: true, suppressSelectionSync: true });
        await selectItem(data.new_name || cleanBase, true, { skipDirtyCheck: true });
      } catch (error) {
        committed = false;
        input.disabled = false;
        input.focus();
        input.select();
        throw error;
      }
    };

    input.addEventListener("click", (event) => event.stopPropagation());
    input.addEventListener("dblclick", (event) => event.stopPropagation());
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        commit().catch(showError || console.error);
      } else if (event.key === "Escape") {
        event.preventDefault();
        committed = true;
        restore();
      }
    });
    input.addEventListener("blur", () => {
      commit().catch(showError || console.error);
    });
  }

  function scrollSelectedItemIntoView(block = "center") {
    if (!state.selectedName) return;
    const activeCard = refs.itemList.querySelector(`.item-card[data-name="${CSS.escape(state.selectedName)}"]`);
    if (!activeCard) return;
    if (block === "nearest") {
      const listRect = refs.itemList.getBoundingClientRect();
      const cardRect = activeCard.getBoundingClientRect();
      const clippedTop = cardRect.top < listRect.top;
      const clippedBottom = cardRect.bottom > listRect.bottom;
      if (!clippedTop && !clippedBottom) return;
      if (clippedTop) {
        refs.itemList.scrollTop -= listRect.top - cardRect.top;
      } else {
        refs.itemList.scrollTop += cardRect.bottom - listRect.bottom;
      }
      return;
    }
    activeCard.scrollIntoView({ block, inline: "nearest" });
  }

  function updateItemCardActiveState() {
    refs.itemList.querySelectorAll(".item-card").forEach((card) => {
      card.classList.toggle("active", card.dataset.name === state.selectedName);
    });
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

  function existingPreviewRoles() {
    const item = state.currentItem;
    if (!item) return [];
    return [...activeControlRoles(), "result"].filter((role) => item.exists?.[role]);
  }

  function previewRoleLabel(role) {
    return role === "result" ? "原图" : ROLE_LABELS[role] || role;
  }

  function ensureImagePreviewOverlay() {
    if (imagePreview) return imagePreview;

    const root = document.createElement("div");
    root.className = "image-preview-overlay";
    root.hidden = true;
    root.setAttribute("aria-hidden", "true");
    root.innerHTML = `
      <div class="image-preview-stage" data-preview-stage>
        <img class="image-preview-main" data-preview-main alt="">
      </div>
      <button class="image-preview-close" data-preview-close type="button" aria-label="关闭预览">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" aria-hidden="true"><rect width="256" height="256" fill="none"/><line x1="200" y1="56" x2="56" y2="200" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="200" y1="200" x2="56" y2="56" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
      </button>
      <div class="image-preview-controls" data-preview-controls></div>
      <div class="image-preview-minimap" data-preview-minimap>
        <img data-preview-thumb alt="">
        <span class="image-preview-viewport" data-preview-viewport></span>
      </div>
    `;
    document.body.appendChild(root);

    imagePreview = {
      root,
      stage: root.querySelector("[data-preview-stage]"),
      main: root.querySelector("[data-preview-main]"),
      close: root.querySelector("[data-preview-close]"),
      controls: root.querySelector("[data-preview-controls]"),
      minimap: root.querySelector("[data-preview-minimap]"),
      thumb: root.querySelector("[data-preview-thumb]"),
      viewport: root.querySelector("[data-preview-viewport]"),
      role: "",
      panX: 0,
      panY: 0,
      dragging: null,
      minimapDragging: null,
      minimapMetrics: null,
      minimapHideTimer: 0,
    };

    imagePreview.close.addEventListener("click", closeImagePreview);
    root.addEventListener("click", (event) => {
      if (event.target === root) closeImagePreview();
    });
    imagePreview.main.addEventListener("load", () => {
      imagePreview.panX = 0;
      imagePreview.panY = 0;
      imagePreview.main.style.opacity = "1";
      imagePreview.thumb.style.opacity = "1";
      updateImagePreviewLayout();
    });
    imagePreview.stage.addEventListener("pointerdown", startImagePreviewDrag);
    imagePreview.viewport.addEventListener("pointerdown", startImagePreviewMinimapDrag);
    imagePreview.minimap.addEventListener("pointerdown", startImagePreviewMinimapDrag);
    window.addEventListener("pointermove", moveImagePreviewDrag);
    window.addEventListener("pointermove", moveImagePreviewMinimapDrag);
    window.addEventListener("pointerup", stopImagePreviewDrag);
    window.addEventListener("pointerup", stopImagePreviewMinimapDrag);
    window.addEventListener("resize", updateImagePreviewLayout);
    document.addEventListener("keydown", (event) => {
      if (!imagePreview?.root.hidden && event.key === "Escape") closeImagePreview();
    });

    return imagePreview;
  }

  function showImagePreviewMinimap() {
    const preview = ensureImagePreviewOverlay();
    preview.root.classList.add("minimap-visible");
    if (preview.minimapHideTimer) {
      window.clearTimeout(preview.minimapHideTimer);
      preview.minimapHideTimer = 0;
    }
  }

  function scheduleImagePreviewMinimapHide() {
    const preview = imagePreview;
    if (!preview) return;
    if (preview.minimapHideTimer) window.clearTimeout(preview.minimapHideTimer);
    preview.minimapHideTimer = window.setTimeout(() => {
      preview.minimapHideTimer = 0;
      preview.root.classList.remove("minimap-visible");
    }, 3000);
  }

  function openImagePreview(role) {
    const item = state.currentItem;
    if (!item?.exists?.[role]) return;
    const preview = ensureImagePreviewOverlay();
    preview.role = role;
    preview.panX = 0;
    preview.panY = 0;
    preview.root.hidden = false;
    preview.root.setAttribute("aria-hidden", "false");
    document.body.classList.add("image-preview-open");
    renderImagePreviewControls();
    setImagePreviewRole(role);
  }

  function closeImagePreview() {
    if (!imagePreview) return;
    imagePreview.root.hidden = true;
    imagePreview.root.setAttribute("aria-hidden", "true");
    imagePreview.dragging = null;
    imagePreview.main.removeAttribute("src");
    imagePreview.thumb.removeAttribute("src");
    imagePreview.minimapDragging = null;
    imagePreview.minimapMetrics = null;
    if (imagePreview.minimapHideTimer) {
      window.clearTimeout(imagePreview.minimapHideTimer);
      imagePreview.minimapHideTimer = 0;
    }
    imagePreview.root.classList.remove("minimap-visible", "minimap-dragging");
    document.body.classList.remove("image-preview-open");
  }

  function renderImagePreviewControls() {
    const preview = ensureImagePreviewOverlay();
    preview.controls.textContent = "";
    preview.controls.hidden = activeControlCount() === 0;
    if (preview.controls.hidden) return;
    for (const role of existingPreviewRoles()) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.previewRole = role;
      button.textContent = previewRoleLabel(role);
      button.addEventListener("click", () => setImagePreviewRole(role));
      preview.controls.appendChild(button);
    }
  }

  function setImagePreviewRole(role) {
    const preview = ensureImagePreviewOverlay();
    const item = state.currentItem;
    if (!item?.exists?.[role]) return;
    preview.role = role;
    preview.panX = 0;
    preview.panY = 0;
    const src = imageUrl(role, item.name);
    preview.main.alt = `${previewRoleLabel(role)} ${item.name}`;
    preview.thumb.alt = `${previewRoleLabel(role)}缩略图`;
    preview.main.style.opacity = "0";
    preview.thumb.style.opacity = "0";
    preview.viewport.hidden = true;
    preview.main.src = src;
    preview.thumb.src = src;
    preview.controls.querySelectorAll("button[data-preview-role]").forEach((button) => {
      button.classList.toggle("active", button.dataset.previewRole === role);
    });
    updateImagePreviewLayout();
  }

  function previewStageRect() {
    const preview = ensureImagePreviewOverlay();
    const rect = preview.stage.getBoundingClientRect();
    return {
      width: Math.max(0, rect.width),
      height: Math.max(0, rect.height),
    };
  }

  function clampImagePreviewPan() {
    const preview = ensureImagePreviewOverlay();
    const img = preview.main;
    if (!img.naturalWidth || !img.naturalHeight) return;
    const stage = previewStageRect();
    const overflowX = Math.max(0, img.naturalWidth - stage.width) / 2;
    const overflowY = Math.max(0, img.naturalHeight - stage.height) / 2;
    preview.panX = Math.min(overflowX, Math.max(-overflowX, preview.panX));
    preview.panY = Math.min(overflowY, Math.max(-overflowY, preview.panY));
  }

  function updateImagePreviewMinimapSize() {
    const preview = ensureImagePreviewOverlay();
    const img = preview.main;
    if (!img.naturalWidth || !img.naturalHeight) return;
    const style = window.getComputedStyle(preview.root);
    const maxSize = Number.parseFloat(style.getPropertyValue("--image-preview-minimap-size")) || 150;
    const aspectRatio = img.naturalWidth / img.naturalHeight;
    const width = aspectRatio >= 1 ? maxSize : maxSize * aspectRatio;
    const height = aspectRatio >= 1 ? maxSize / aspectRatio : maxSize;
    preview.minimap.style.width = `${width}px`;
    preview.minimap.style.height = `${height}px`;
  }

  function updateImagePreviewLayout() {
    if (!imagePreview || imagePreview.root.hidden) return;
    const preview = imagePreview;
    const img = preview.main;
    if (!img.naturalWidth || !img.naturalHeight) return;
    clampImagePreviewPan();
    updateImagePreviewMinimapSize();
    img.style.width = `${img.naturalWidth}px`;
    img.style.height = `${img.naturalHeight}px`;
    img.style.transform = `translate(-50%, -50%) translate(${preview.panX}px, ${preview.panY}px)`;
    updateImagePreviewViewport();
  }

  function updateImagePreviewViewport() {
    const preview = ensureImagePreviewOverlay();
    const img = preview.main;
    const mini = preview.minimap.getBoundingClientRect();
    const stage = previewStageRect();
    if (!img.naturalWidth || !img.naturalHeight || !mini.width || !mini.height) {
      preview.viewport.hidden = true;
      return;
    }

    const imageScale = Math.min(mini.width / img.naturalWidth, mini.height / img.naturalHeight);
    const thumbWidth = img.naturalWidth * imageScale;
    const thumbHeight = img.naturalHeight * imageScale;
    const thumbX = (mini.width - thumbWidth) / 2;
    const thumbY = (mini.height - thumbHeight) / 2;
    preview.minimapMetrics = {
      imageScale,
      thumbX,
      thumbY,
      thumbWidth,
      thumbHeight,
      stageWidth: stage.width,
      stageHeight: stage.height,
    };
    const clippedX = img.naturalWidth > stage.width;
    const clippedY = img.naturalHeight > stage.height;
    if (!clippedX && !clippedY) {
      preview.viewport.hidden = true;
      return;
    }

    const visibleWidth = Math.min(stage.width, img.naturalWidth);
    const visibleHeight = Math.min(stage.height, img.naturalHeight);
    const imageLeft = clippedX ? (img.naturalWidth - stage.width) / 2 - preview.panX : 0;
    const imageTop = clippedY ? (img.naturalHeight - stage.height) / 2 - preview.panY : 0;
    preview.viewport.hidden = false;
    preview.viewport.style.left = `${thumbX + imageLeft * imageScale}px`;
    preview.viewport.style.top = `${thumbY + imageTop * imageScale}px`;
    preview.viewport.style.width = `${visibleWidth * imageScale}px`;
    preview.viewport.style.height = `${visibleHeight * imageScale}px`;
  }

  function setPreviewPanFromMinimapPoint(clientX, clientY) {
    const preview = ensureImagePreviewOverlay();
    const img = preview.main;
    const metrics = preview.minimapMetrics;
    if (!img.naturalWidth || !img.naturalHeight || !metrics) return;
    const mini = preview.minimap.getBoundingClientRect();
    const imageX = (clientX - mini.left - metrics.thumbX) / metrics.imageScale;
    const imageY = (clientY - mini.top - metrics.thumbY) / metrics.imageScale;
    const maxPanX = Math.max(0, img.naturalWidth - metrics.stageWidth) / 2;
    const maxPanY = Math.max(0, img.naturalHeight - metrics.stageHeight) / 2;
    preview.panX = maxPanX ? img.naturalWidth / 2 - imageX : 0;
    preview.panY = maxPanY ? img.naturalHeight / 2 - imageY : 0;
    updateImagePreviewLayout();
  }

  function startImagePreviewDrag(event) {
    const preview = ensureImagePreviewOverlay();
    if (event.button !== 0 || !preview.main.naturalWidth) return;
    event.preventDefault();
    preview.dragging = {
      x: event.clientX,
      y: event.clientY,
      panX: preview.panX,
      panY: preview.panY,
    };
    showImagePreviewMinimap();
    preview.stage.setPointerCapture?.(event.pointerId);
    preview.root.classList.add("dragging");
  }

  function moveImagePreviewDrag(event) {
    const preview = imagePreview;
    if (!preview?.dragging) return;
    preview.panX = preview.dragging.panX + event.clientX - preview.dragging.x;
    preview.panY = preview.dragging.panY + event.clientY - preview.dragging.y;
    updateImagePreviewLayout();
  }

  function stopImagePreviewDrag() {
    if (!imagePreview?.dragging) return;
    imagePreview.dragging = null;
    imagePreview.root.classList.remove("dragging");
    scheduleImagePreviewMinimapHide();
  }

  function startImagePreviewMinimapDrag(event) {
    const preview = ensureImagePreviewOverlay();
    if (event.button !== 0 || preview.viewport.hidden) return;
    event.preventDefault();
    event.stopPropagation();
    preview.minimapDragging = true;
    showImagePreviewMinimap();
    preview.root.classList.add("minimap-dragging");
    preview.minimap.setPointerCapture?.(event.pointerId);
    setPreviewPanFromMinimapPoint(event.clientX, event.clientY);
  }

  function moveImagePreviewMinimapDrag(event) {
    if (!imagePreview?.minimapDragging) return;
    setPreviewPanFromMinimapPoint(event.clientX, event.clientY);
  }

  function stopImagePreviewMinimapDrag() {
    if (!imagePreview?.minimapDragging) return;
    imagePreview.minimapDragging = null;
    imagePreview.root.classList.remove("minimap-dragging");
    scheduleImagePreviewMinimapHide();
  }

  function renderItemList() {
    ensureItemContextMenuEvents();
    renderFolderFilters();
    const items = filteredItems();
    state.visibleItems = items;
    disconnectItemThumbObserver();
    refs.itemList.textContent = "";
    refs.listStats.textContent = state.itemFolderFilter ? `${items.length}/${state.items.length} 项` : `${items.length} 项`;
    renderWorkspaceSummary();
    if (refs.metricFiltered) refs.metricFiltered.textContent = `${items.length || 0}`;

    for (const item of items) {
      const thumbRoles = state.listThumbMode === "combined" && activeControlCount() > 0
        ? [...activeControlRoles(), "result"]
        : ["result"];
      const card = document.createElement("article");
      card.className = `item-card${item.name === state.selectedName ? " active" : ""}${thumbRoles.length > 1 ? " multi-thumb" : ""}`;
      card.dataset.name = item.name;
      card.draggable = true;
      card.title = "双击重命名图片";
      card.addEventListener("dragstart", (event) => {
        if (event.target.closest(".item-rename-input")) {
          event.preventDefault();
          return;
        }
        event.dataTransfer?.setData(ITEM_DRAG_TYPE, item.name);
        event.dataTransfer?.setData("text/plain", item.name);
        if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
        card.classList.add("dragging");
      });
      card.addEventListener("dragend", () => {
        card.classList.remove("dragging");
        refs.itemFolderFilters?.querySelectorAll(".drag-over").forEach((node) => node.classList.remove("drag-over"));
      });
      const thumbs = document.createElement("div");
      thumbs.className = thumbRoles.length > 1 ? "item-thumb-grid" : "item-thumb-single";
      thumbs.style.setProperty("--thumb-count", String(thumbRoles.length));
      for (const role of thumbRoles) {
        if (item.exists[role]) {
          thumbs.appendChild(createItemThumbSlot(item, role));
        } else {
          const placeholder = document.createElement("div");
          placeholder.className = "item-thumb-empty";
          placeholder.textContent = thumbRoles.length > 1 ? (ROLE_LABELS[role] || role).replace(/\s+/g, "") : "无结果";
          thumbs.appendChild(placeholder);
        }
      }
      card.appendChild(thumbs);

      const right = document.createElement("div");
      right.className = "item-card-main";
      const title = document.createElement("div");
      title.className = "item-title";
      appendHighlightedText(title, displayItemListName(item.name), state.listSearchMode === "name" ? state.segmentQuery : "");
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
      card.addEventListener("click", (event) => {
        if (event.target.closest(".item-rename-input")) return;
        if (event.detail > 1) {
          event.preventDefault();
          beginInlineItemRename(item, title).catch(showError || console.error);
          return;
        }
        selectItem(item.name, false).catch(showError || console.error);
      });
      card.addEventListener("dblclick", (event) => {
        if (event.target.closest(".item-rename-input")) return;
        event.preventDefault();
        event.stopPropagation();
        beginInlineItemRename(item, title).catch(showError || console.error);
      });
      card.addEventListener("contextmenu", (event) => {
        if (event.target.closest(".item-rename-input")) return;
        openItemContextMenu(event, item, title);
      });
      refs.itemList.appendChild(card);
    }

    scrollSelectedItemIntoView("nearest");
  }

  function renderSelectionSummary() {
    const item = state.currentItem;
    const selectedIndex = item ? state.items.findIndex((candidate) => candidate.name === item.name) + 1 : 0;
    refs.focusStat.textContent = selectedIndex > 0 ? `${selectedIndex}/${state.items.length || 0}` : `0/${state.items.length || 0}`;
    if (refs.overviewCurrentName) refs.overviewCurrentName.textContent = item ? item.name : "未选择图片";
    if (refs.overviewCurrentMeta) {
      refs.overviewCurrentMeta.textContent = item
        ? [
            `TXT ${item.exists.txt ? "已存在" : "未创建"}`,
            ...activeControlRoles().map((role) => `${ROLE_LABELS[role]} ${item.exists[role] ? "有" : "无"}`),
            `结果图 ${item.exists.result ? "有" : "无"}`,
          ].join(" · ")
        : "加载工作区后，在浏览区选择条目开始编辑。";
    }
  }

  function viewerResolutionSummary(item) {
    if (!item) return "";
    const resultRes = item.resolution.result;
    if (!Array.isArray(resultRes)) return "结果图分辨率: 未读取";

    const comparisons = activeControlRoles()
      .map((role) => ({ role, size: item.resolution[role] }))
      .filter((row) => Array.isArray(row.size));

    if (!comparisons.length) return `结果图分辨率: ${resultRes[0]}×${resultRes[1]}`;

    const mismatches = comparisons.filter(
      (row) => row.size[0] !== resultRes[0] || row.size[1] !== resultRes[1],
    );
    if (!mismatches.length) return `控制图与结果图分辨率一致: ${resultRes[0]}×${resultRes[1]}`;
    return mismatches
      .map((row) => `${ROLE_LABELS[row.role]} ${row.size[0]}×${row.size[1]} 与结果图 ${resultRes[0]}×${resultRes[1]} 不一致`)
      .join(" · ");
  }

  function renderCurrentMeta(item) {
    refs.currentMeta.textContent = "";
    if (!item) {
      refs.currentMeta.textContent = "选择左侧条目开始浏览。";
      return;
    }

    const statusLine = document.createElement("span");
    statusLine.className = "current-meta-line";
    statusLine.textContent = [
      `TXT: ${item.exists.txt ? "已存在" : "未创建"}`,
      ...activeControlRoles().map((role) => `${ROLE_LABELS[role]}: ${item.exists[role] ? "有" : "无"}`),
      `结果图: ${item.exists.result ? "有" : "无"}`,
    ].join("，");

    const resolutionLine = document.createElement("span");
    resolutionLine.className = "current-meta-line";
    resolutionLine.textContent = viewerResolutionSummary(item);

    refs.currentMeta.append(statusLine, resolutionLine);
  }

  function clearViewerRoleDragClasses() {
    refs.viewerGrid.querySelectorAll(".role-dragging, .role-drop-target").forEach((node) => {
      node.classList.remove("role-dragging", "role-drop-target");
    });
  }

  function canSwapViewerRoles(sourceRole, targetRole) {
    const item = state.currentItem;
    return Boolean(
      item
      && sourceRole
      && targetRole
      && sourceRole !== targetRole
      && item.exists?.[sourceRole]
      && item.exists?.[targetRole],
    );
  }

  async function swapViewerItemRoles(sourceRole, targetRole) {
    if (!canSwapViewerRoles(sourceRole, targetRole)) {
      setAiStatusLine("需要两张已存在的图片才能对调控制图/结果图。");
      return;
    }
    if (!(await confirmDiscardCaptionChanges())) return;
    const name = state.currentItem.name;
    const data = await apiPost("/api/item/swap-roles", {
      name,
      source_role: sourceRole,
      target_role: targetRole,
    });
    if (data.workspace) applyWorkspaceSummary(data.workspace);
    if (data.item) state.currentItem = data.item;
    setAiStatusLine(`已对调：${ROLE_LABELS[sourceRole] || sourceRole} <-> ${ROLE_LABELS[targetRole] || targetRole}`);
    await refreshItems({ skipDirtyCheck: true });
  }

  function ensureViewerRoleDragEvents() {
    if (!refs.viewerGrid || state.viewerRoleDragBound) return;
    state.viewerRoleDragBound = true;
    refs.viewerGrid.addEventListener("dragstart", (event) => {
      const card = event.target.closest(".image-card");
      const role = card?.dataset.role || "";
      if (!card || !state.currentItem?.exists?.[role]) {
        event.preventDefault();
        return;
      }
      event.dataTransfer?.setData(VIEWER_ROLE_DRAG_TYPE, role);
      event.dataTransfer?.setData("text/plain", role);
      if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
      state.viewerRoleDragging = role;
      card.classList.add("role-dragging");
    });
    refs.viewerGrid.addEventListener("dragend", () => {
      state.viewerRoleDragging = "";
      clearViewerRoleDragClasses();
    });
    refs.viewerGrid.addEventListener("dragover", (event) => {
      const card = event.target.closest(".image-card");
      if (!card || !Array.from(event.dataTransfer?.types || []).includes(VIEWER_ROLE_DRAG_TYPE)) return;
      const sourceRole = state.viewerRoleDragging || "";
      const targetRole = card.dataset.role || "";
      if (!canSwapViewerRoles(sourceRole, targetRole)) return;
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
      refs.viewerGrid.querySelectorAll(".role-drop-target").forEach((node) => {
        if (node !== card) node.classList.remove("role-drop-target");
      });
      card.classList.add("role-drop-target");
    });
    refs.viewerGrid.addEventListener("dragleave", (event) => {
      const card = event.target.closest(".image-card");
      if (!card || card.contains(event.relatedTarget)) return;
      card.classList.remove("role-drop-target");
    });
    refs.viewerGrid.addEventListener("drop", (event) => {
      const card = event.target.closest(".image-card");
      if (!card) return;
      const sourceRole = event.dataTransfer?.getData(VIEWER_ROLE_DRAG_TYPE) || "";
      const targetRole = card.dataset.role || "";
      state.viewerRoleDragging = "";
      clearViewerRoleDragClasses();
      if (!canSwapViewerRoles(sourceRole, targetRole)) return;
      event.preventDefault();
      swapViewerItemRoles(sourceRole, targetRole).catch(showError || console.error);
    });
  }

  function renderViewer() {
    const item = state.currentItem;
    ensureViewerRoleDragEvents();
    ensureViewerResizeObserver();
    refs.viewerGrid.dataset.mode = state.viewMode;
    refs.viewerGrid.dataset.imageMode = "fit";
    refs.currentName.textContent = item ? item.name : "未选择图片";
    renderCurrentMeta(item);

    const controlCount = activeControlCount();
    refs.viewModeGroup.querySelectorAll("button").forEach((button) => {
      button.classList.toggle("active", controlCount > 0 && button.dataset.mode === state.viewMode);
    });

    const visibleRoles =
      controlCount === 0
        ? ["result"]
        : state.viewMode === "one"
          ? ["result"]
          : state.viewMode === "two"
            ? ["control1", "result"]
            : state.viewMode === "three"
              ? ["control1", "control2", "result"]
              : ["control1", "control2", "control3", "result"];

    refs.viewerGrid.querySelectorAll(".image-card").forEach((card) => {
      const role = card.dataset.role;
      card.style.display = visibleRoles.includes(role) ? "flex" : "none";
      card.draggable = Boolean(item?.exists?.[role]);
      card.classList.toggle("role-draggable", Boolean(item?.exists?.[role]));
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
      img.draggable = false;
      img.title = "点击打开大图预览";
      img.addEventListener("load", () => updateViewerImageFit(img));
      img.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        openImagePreview(role);
      });
      stage.appendChild(img);
      const size = item.resolution[role];
      resLabel.textContent = Array.isArray(size) ? `${size[0]}×${size[1]}` : "";
    });

    const canProcess = Boolean(item);
    if (refs.viewerScaleBtn) refs.viewerScaleBtn.disabled = !canProcess;
    if (refs.viewerMatchResultBtn) refs.viewerMatchResultBtn.disabled = !canProcess || !item.exists.result;

    if (!item) {
      renderSelectionSummary();
      return;
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
    const data = await apiGet("/api/items", {
      filter: state.filter,
      tag: state.segmentQuery,
      search_mode: state.listSearchMode === "name" ? "name" : "phrase",
      match_mode: state.listSearchMatchMode === "exact" ? "exact" : "contains",
    });
    if (data.workspace) state.workspace = data.workspace;
    state.items = data.items;
    state.itemStats = data.stats;
    state.globalSegments = data.global_segments || data.global_tags || [];
    renderFilters();
    renderItemList();
    renderGlobalTags();
    renderWorkspaceSummary();

    if (!state.items.length || !state.visibleItems.length) {
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

    const stillExists = state.visibleItems.some((item) => item.name === state.selectedName);
    const nextName = stillExists ? state.selectedName : state.visibleItems[0].name;
    await selectItem(nextName, !stillExists, { skipDirtyCheck });
  }

  async function selectItem(name, rerenderList = true, options = {}) {
    const { skipDirtyCheck = false } = options;
    if (!skipDirtyCheck && name !== state.selectedName) {
      const ok = await confirmDiscardCaptionChanges();
      if (!ok) return;
    }
    state.selectedName = name;
    if (!rerenderList) updateItemCardActiveState();
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
    const previousKey = state.workspace?.workspace_key || "";
    state.workspace = workspace;
    const nextKey = state.workspace?.workspace_key || "";
    state.workspaceImageVersion = (state.workspaceImageVersion || 0) + 1;
    state.imageRefreshToken = `${Date.now()}-${state.workspaceImageVersion}-${nextKey || previousKey}`;
    const dirs = state.workspace?.dirs || {};
    const settings = state.workspace?.settings || {};
    const hasLoadedWorkspace = Object.values(dirs).some(Boolean);
    if (hasLoadedWorkspace) {
      refs.controlCount.value = String(settings.control_count ?? refs.controlCount.value ?? "1");
    }
    refs.ignoreTokensInput.value = Array.isArray(settings.ignore_tokens)
      ? settings.ignore_tokens.join(", ")
      : refs.ignoreTokensInput.value;
    refs.control1Dir.value = workspacePathRelativeToBrowserRoot?.(dirs.control1) || dirs.control1 || "";
    refs.control2Dir.value = workspacePathRelativeToBrowserRoot?.(dirs.control2) || dirs.control2 || "";
    refs.control3Dir.value = workspacePathRelativeToBrowserRoot?.(dirs.control3) || dirs.control3 || "";
    refs.resultDir.value = workspacePathRelativeToBrowserRoot?.(dirs.result) || dirs.result || "";
    if (refs.swapControlDir && !refs.swapControlDir.value.trim() && dirs.control1) {
      refs.swapControlDir.value = dirs.control1;
    }
    if (refs.swapResultDir && !refs.swapResultDir.value.trim() && dirs.result) {
      refs.swapResultDir.value = dirs.result;
    }
    seedWorkspaceBrowserRootFromInputs();
    updateControlFieldVisibility();
    renderWorkspaceBrowser();
    renderWorkspaceSummary();
  }

  function workspaceOpenPayloadFromInputs() {
    return {
      control1_dir: resolveWorkspaceInputPath?.(refs.control1Dir.value.trim()) || refs.control1Dir.value.trim(),
      control2_dir: resolveWorkspaceInputPath?.(refs.control2Dir.value.trim()) || refs.control2Dir.value.trim(),
      control3_dir: resolveWorkspaceInputPath?.(refs.control3Dir.value.trim()) || refs.control3Dir.value.trim(),
      result_dir: resolveWorkspaceInputPath?.(refs.resultDir.value.trim()) || refs.resultDir.value.trim(),
      control_count: Number(refs.controlCount.value ?? 1),
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
      control_count: Number(refs.controlCount.value ?? 1),
    });
    applyWorkspaceSummary(data.workspace);
    await refreshItems({ skipDirtyCheck: true });
    refs.mergeStatus.textContent = `已追加 ${data.merged || 0} 项到当前工作区`;
    setAiStatusLine(`已追加数据集：${data.merged || 0} 项`);
  }

  function updateControlFieldVisibility() {
    const count = activeControlCount();
    const previousCount = Number(state.workspace?.settings?.control_count ?? refs.controlCount.dataset.previousCount ?? 1);
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
        (filter === "no_control1" && count < 1) ||
        (filter === "no_control2" && count < 2) ||
        (filter === "no_control3" && count < 3);
      button.style.display = shouldHide ? "none" : "";
    });
    if (
      (state.filter === "no_control1" && count < 1) ||
      (state.filter === "no_control2" && count < 2) ||
      (state.filter === "no_control3" && count < 3)
    ) {
      state.filter = "all";
    }
    syncWorkspaceBrowserTargetVisibility();

    const allowedModes = count === 0 ? ["one"] : count === 1 ? ["one", "two"] : count === 2 ? ["one", "two", "three"] : ["one", "two", "three", "four"];
    refs.viewModeGroup.style.display = count > 0 ? "" : "none";
    refs.viewModeGroup.querySelectorAll("button[data-mode]").forEach((button) => {
      button.style.display = count > 0 && allowedModes.includes(button.dataset.mode) ? "" : "none";
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
    if (state.items.length) {
      renderItemList();
    }
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
