export function createEditorModule({
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
  onGlobalTagClick,
}) {
  const GLOBAL_TAG_DRAG_TYPE = "application/x-vds-global-tag";
  const GLOBAL_TAG_ROW_HEIGHT = 42;
  const GLOBAL_TAG_ROW_GAP = 8;
  const GLOBAL_TAG_IDLE_OVERSCAN = 1;
  const GLOBAL_TAG_SCROLL_OVERSCAN = 5;
  const GLOBAL_TAG_SCROLL_IDLE_MS = 140;
  let globalTagDragGhost = null;
  let globalTagScrollFrame = 0;
  let globalTagScrollEndTimer = 0;
  let globalTagViewportSignature = "";
  let globalTagScrolling = false;

  function normalizeGlobalTagQuery(value = state.globalTagQuery) {
    return `${value || ""}`.trim().toLowerCase();
  }

  function removeGlobalTagDragGhost() {
    globalTagDragGhost?.remove();
    globalTagDragGhost = null;
  }

  function updateGlobalTagDragGhost(event) {
    const drag = state.globalTagPointerDrag;
    if (!drag?.segment) return;
    if (!globalTagDragGhost) {
      globalTagDragGhost = document.createElement("div");
      globalTagDragGhost.className = "global-tag-drag-ghost";
      globalTagDragGhost.textContent = drag.segment;
      document.body.appendChild(globalTagDragGhost);
    }
    globalTagDragGhost.style.transform = `translate3d(${event.clientX + 14}px, ${event.clientY + 14}px, 0)`;
  }

  function renderPromptTemplateSelectors() {
    document.querySelectorAll(".promptTemplateSelect").forEach((select) => {
      const previous = select.value;
      select.innerHTML = state.promptTemplates
        .map((item) => `<option value="${item.id}">${item.name}</option>`)
        .join("");
      if (state.promptTemplates.some((item) => item.id === previous)) {
        select.value = previous;
      }
      select.dispatchEvent(new Event("vds-select-sync", { bubbles: true }));
    });
  }

  function templateById(id) {
    return state.promptTemplates.find((item) => item.id === id) || null;
  }

  function selectedTemplateNameFor(targetId) {
    const row = document.querySelector(`.template-row[data-template-target="${targetId}"]`);
    const select = row?.querySelector(".promptTemplateSelect");
    const template = templateById(select?.value);
    return template?.name || "中文·极简变化";
  }

  function writeSegmentsToText(segments) {
    state.currentText = normalizeCaptionText(segments.join(", "));
    if (refs.captionEditor) refs.captionEditor.value = state.currentText;
    syncSegmentsFromText();
    syncCaptionDirty();
    updateCaptionSearchHighlight();
    scheduleCaptionAutosave();
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
      const mark = document.createElement("mark");
      mark.className = "caption-search-hit";
      mark.textContent = value.slice(matchIndex, matchIndex + needle.length);
      parent.appendChild(mark);
      index = matchIndex + needle.length;
      matchIndex = lowerValue.indexOf(lowerNeedle, index);
    }
    if (index < value.length) {
      parent.appendChild(document.createTextNode(value.slice(index)));
    }
  }

  function updateCaptionSearchHighlight() {
    if (!refs.captionHighlight || !refs.captionEditor) return;
    const query = `${state.segmentQuery || ""}`.trim();
    refs.captionHighlight.textContent = "";
    refs.captionHighlight.classList.toggle("active", Boolean(query));
    refs.captionEditor.classList.toggle("search-active", Boolean(query));
    if (!query) return;
    appendHighlightedText(refs.captionHighlight, refs.captionEditor.value || state.currentText || "", query);
    refs.captionHighlight.appendChild(document.createTextNode("\n"));
    refs.captionHighlight.scrollTop = refs.captionEditor.scrollTop;
    refs.captionHighlight.scrollLeft = refs.captionEditor.scrollLeft;
  }

  function renderTags() {
    refs.tagChips.innerHTML = "";
    const searchQuery = `${state.segmentQuery || ""}`.trim().toLowerCase();
    updateCaptionSearchHighlight();
    state.currentSegments.forEach((segment, index) => {
      const row = document.createElement("div");
      row.className = `chip${searchQuery && segment.toLowerCase().includes(searchQuery) ? " search-match" : ""}`;
      const input = document.createElement("input");
      input.className = "chip-input";
      input.value = segment;
      input.addEventListener("change", () => {
        const next = [...state.currentSegments];
        next[index] = input.value.trim();
        writeSegmentsToText(next.filter(Boolean));
        renderTags();
      });
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "chip-x";
      remove.textContent = "×";
      remove.addEventListener("click", () => {
        const next = state.currentSegments.filter((_, i) => i !== index);
        writeSegmentsToText(next);
        renderTags();
      });
      row.appendChild(input);
      row.appendChild(remove);
      refs.tagChips.appendChild(row);
    });
  }

  function appendSegmentsToCaption(segments) {
    const additions = (segments || []).map((segment) => `${segment || ""}`.trim()).filter(Boolean);
    if (!additions.length) return;
    state.currentText = `${state.currentText || ""}`.trim();
    const prefix = state.currentText ? ", " : "";
    state.currentText = normalizeCaptionText(`${state.currentText}${prefix}${additions.join(", ")}`);
    if (refs.captionEditor) refs.captionEditor.value = state.currentText;
    syncSegmentsFromText();
    syncCaptionDirty();
    renderTags();
    scheduleCaptionAutosave();
  }

  function appendQuickTagToCaption(value) {
    const text = `${value ?? ""}`;
    if (!text) return;
    state.currentText = normalizeCaptionText(`${state.currentText || ""}${text}`);
    if (refs.captionEditor) refs.captionEditor.value = state.currentText;
    syncSegmentsFromText();
    syncCaptionDirty();
    renderTags();
    scheduleCaptionAutosave();
  }

  function appendDraggedGlobalTagToCaption(value) {
    const segment = `${value ?? ""}`.trim();
    if (!segment) return;
    const current = `${state.currentText || refs.captionEditor?.value || ""}`.replace(/\s+$/, "");
    const separator = current ? (/[，,;；]\s*$/.test(current) ? " " : ", ") : "";
    state.currentText = normalizeCaptionText(`${current}${separator}${segment}`);
    if (refs.captionEditor) {
      refs.captionEditor.value = state.currentText;
      refs.captionEditor.focus();
      refs.captionEditor.selectionStart = refs.captionEditor.value.length;
      refs.captionEditor.selectionEnd = refs.captionEditor.value.length;
    }
    syncSegmentsFromText();
    syncCaptionDirty();
    renderTags();
    scheduleCaptionAutosave();
  }

  function eventHasGlobalTagDrag(event) {
    const types = Array.from(event.dataTransfer?.types || []);
    return Boolean(state.globalTagDragging) || types.includes(GLOBAL_TAG_DRAG_TYPE);
  }

  function readGlobalTagDragValue(event) {
    return event.dataTransfer?.getData(GLOBAL_TAG_DRAG_TYPE) || state.globalTagDragging || event.dataTransfer?.getData("text/plain") || "";
  }

  function isGlobalTagDropTarget(target) {
    return target instanceof Element && Boolean(target.closest("#captionEditor, .edit-card-body"));
  }

  function isGlobalTagDropPoint(event) {
    const x = Number(event.clientX);
    const y = Number(event.clientY);
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return isGlobalTagDropTarget(event.target);
    }

    const hit = document.elementFromPoint(x, y);
    if (isGlobalTagDropTarget(hit)) return true;

    const targets = [refs.captionEditor, document.querySelector(".edit-card-body")].filter(Boolean);
    return targets.some((target) => {
      const rect = target.getBoundingClientRect();
      return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
    });
  }

  function bindGlobalTagDropTarget() {
    const suppressNextGlobalTagClick = () => {
      state.globalTagSuppressClick = true;
      window.setTimeout(() => {
        state.globalTagSuppressClick = false;
      }, 0);
    };

    const finishPointerLikeGlobalTagDrop = (event) => {
      const drag = state.globalTagPointerDrag;
      if (!drag?.segment) return;
      state.globalTagPointerDrag = null;
      drag.source?.classList.remove("dragging");
      removeGlobalTagDragGhost();
      refs.captionEditor?.classList.remove("drag-over");
      const moved = Math.abs(event.clientX - drag.startX) + Math.abs(event.clientY - drag.startY);
      if (moved >= 8) suppressNextGlobalTagClick();
      if (moved < 8 || !isGlobalTagDropPoint(event)) return;
      event.preventDefault();
      appendDraggedGlobalTagToCaption(drag.segment);
    };

    const movePointerLikeGlobalTagDrag = (event) => {
      const drag = state.globalTagPointerDrag;
      if (!drag?.segment) return;
      const moved = Math.abs(event.clientX - drag.startX) + Math.abs(event.clientY - drag.startY);
      if (moved >= 4) {
        drag.source?.classList.add("dragging");
        updateGlobalTagDragGhost(event);
      }
      refs.captionEditor?.classList.toggle("drag-over", isGlobalTagDropPoint(event));
    };

    const targets = [refs.captionEditor, document.querySelector(".edit-card-body")].filter(Boolean);
    targets.forEach((target) => {
      target.addEventListener("dragover", (event) => {
        if (!eventHasGlobalTagDrag(event)) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
        refs.captionEditor?.classList.add("drag-over");
      });
      target.addEventListener("dragleave", (event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          refs.captionEditor?.classList.remove("drag-over");
        }
      });
      target.addEventListener("drop", (event) => {
        const segment = readGlobalTagDragValue(event);
        if (!segment) return;
        event.preventDefault();
        event.stopPropagation();
        refs.captionEditor?.classList.remove("drag-over");
        appendDraggedGlobalTagToCaption(segment);
      });
    });

    document.addEventListener("dragover", (event) => {
      if (!state.globalTagDragging || !isGlobalTagDropPoint(event)) return;
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
      refs.captionEditor?.classList.add("drag-over");
    }, true);

    document.addEventListener("drop", (event) => {
      if (!state.globalTagDragging || !isGlobalTagDropPoint(event)) return;
      event.preventDefault();
      event.stopPropagation();
      const segment = readGlobalTagDragValue(event);
      refs.captionEditor?.classList.remove("drag-over");
      state.globalTagDragging = "";
      appendDraggedGlobalTagToCaption(segment);
    }, true);

    document.addEventListener("pointermove", (event) => {
      movePointerLikeGlobalTagDrag(event);
    }, true);

    document.addEventListener("mousemove", (event) => {
      movePointerLikeGlobalTagDrag(event);
    }, true);

    document.addEventListener("pointerup", finishPointerLikeGlobalTagDrop, true);
    document.addEventListener("mouseup", finishPointerLikeGlobalTagDrop, true);
    window.addEventListener("blur", () => {
      state.globalTagPointerDrag = null;
      document.querySelector(".global-tag-row.dragging")?.classList.remove("dragging");
      refs.captionEditor?.classList.remove("drag-over");
      removeGlobalTagDragGhost();
    });
  }

  bindGlobalTagDropTarget();

  refs.captionEditor?.addEventListener("scroll", () => {
    if (!refs.captionHighlight) return;
    refs.captionHighlight.scrollTop = refs.captionEditor.scrollTop;
    refs.captionHighlight.scrollLeft = refs.captionEditor.scrollLeft;
  });

  refs.globalTagSearch?.addEventListener("input", () => {
    state.globalTagQuery = refs.globalTagSearch.value;
    renderGlobalTags();
  });

  refs.globalTagList?.addEventListener("scroll", () => {
    if (!Array.isArray(state.globalTagVirtualRows)) return;
    globalTagScrolling = true;
    if (globalTagScrollEndTimer) window.clearTimeout(globalTagScrollEndTimer);
    globalTagScrollEndTimer = window.setTimeout(() => {
      globalTagScrollEndTimer = 0;
      globalTagScrolling = false;
      globalTagViewportSignature = "";
      renderGlobalTagViewport();
    }, GLOBAL_TAG_SCROLL_IDLE_MS);
    scheduleGlobalTagViewportRender();
  });

  function setQuickTagsDirty(value = true) {
    state.quickTagsDirty = Boolean(value);
    if (refs.quickTagSaveBtn) {
      refs.quickTagSaveBtn.classList.toggle("dirty", state.quickTagsDirty);
    }
  }

  function renderQuickTags() {
    refs.quickTagPanel?.classList.toggle("collapsed", state.quickTagsCollapsed);
    refs.quickTagToggleBtn?.setAttribute("aria-expanded", state.quickTagsCollapsed ? "false" : "true");
    if (refs.quickTagToggleBtn) {
      refs.quickTagToggleBtn.textContent = state.quickTagsCollapsed ? "快捷标注 +" : "快捷标注 -";
    }
    setQuickTagsDirty(state.quickTagsDirty);
    refs.quickTagGrid.textContent = "";

    state.quickTags.forEach((tag, index) => {
      const row = document.createElement("div");
      row.className = "quick-tag-item";
      row.draggable = true;
      row.dataset.quickTagIndex = String(index);

      const handle = document.createElement("span");
      handle.className = "quick-tag-handle";
      handle.textContent = "::";

      const button = document.createElement("button");
      button.type = "button";
      button.className = "button-ghost quick-tag-btn";
      button.textContent = tag;
      button.addEventListener("click", () => scheduleQuickTagAppend(index));
      button.addEventListener("dblclick", (event) => {
        event.preventDefault();
        window.clearTimeout(state.quickTagClickTimer);
        state.quickTagClickTimer = null;
        editQuickTag(index);
      });

      row.addEventListener("dragstart", (event) => {
        state.quickTagDragIndex = index;
        row.classList.add("dragging");
        event.dataTransfer?.setData("text/plain", String(index));
        if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
      });
      row.addEventListener("dragend", () => {
        state.quickTagDragIndex = null;
        row.classList.remove("dragging");
        refs.quickTagGrid.querySelectorAll(".quick-tag-item.over").forEach((node) => node.classList.remove("over"));
      });
      row.addEventListener("dragover", (event) => {
        event.preventDefault();
        row.classList.add("over");
      });
      row.addEventListener("dragleave", () => row.classList.remove("over"));
      row.addEventListener("drop", (event) => {
        event.preventDefault();
        row.classList.remove("over");
        const fromIndex = Number(event.dataTransfer?.getData("text/plain") || state.quickTagDragIndex);
        moveQuickTag(fromIndex, index);
      });

      row.appendChild(handle);
      row.appendChild(button);
      refs.quickTagGrid.appendChild(row);
    });
  }

  function toggleQuickTags(force = null) {
    state.quickTagsCollapsed = force === null ? !state.quickTagsCollapsed : Boolean(force);
    saveStored(STORAGE_KEYS.quickTagsCollapsed, state.quickTagsCollapsed ? "true" : "false");
    renderQuickTags();
  }

  function moveQuickTag(fromIndex, toIndex) {
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) return;
    if (fromIndex >= state.quickTags.length || toIndex >= state.quickTags.length) return;
    const next = [...state.quickTags];
    const [item] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, item);
    state.quickTags = next;
    setQuickTagsDirty(true);
    renderQuickTags();
  }

  function editQuickTag(index) {
    if (index < 0 || index >= state.quickTags.length) return;
    toggleQuickTags(false);
    const row = refs.quickTagGrid.querySelector(`[data-quick-tag-index="${index}"]`);
    if (!row) return;
    const button = row.querySelector(".quick-tag-btn");
    if (!button) return;
    const input = document.createElement("input");
    input.className = "quick-tag-edit";
    input.value = state.quickTags[index];
    button.replaceWith(input);
    input.focus();
    input.select();

    let committed = false;
    const commit = () => {
      if (committed) return;
      committed = true;
      const value = input.value;
      if (value.trim()) {
        state.quickTags[index] = value;
      } else {
        state.quickTags.splice(index, 1);
      }
      state.quickTags = cleanQuickTags(state.quickTags);
      setQuickTagsDirty(true);
      renderQuickTags();
    };

    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        commit();
      } else if (event.key === "Escape") {
        committed = true;
        renderQuickTags();
      }
    });
    input.addEventListener("blur", commit);
  }

  function scheduleQuickTagAppend(index) {
    window.clearTimeout(state.quickTagClickTimer);
    state.quickTagClickTimer = window.setTimeout(() => {
      appendQuickTagToCaption(state.quickTags[index] || "");
      state.quickTagClickTimer = null;
    }, 240);
  }

  function createGlobalTagRow(row) {
    const segment = row.segment || row.tag || "";
    const button = document.createElement("button");
    button.type = "button";
    button.draggable = false;
    button.className = `global-tag-row${state.segmentQuery.toLowerCase() === segment.toLowerCase() ? " active" : ""}`;
    button.title = "拖到左侧 Caption 中追加";
    const name = document.createElement("span");
    name.textContent = segment;
    const count = document.createElement("span");
    count.textContent = `${row.count}`;
    button.appendChild(name);
    button.appendChild(count);
    button.addEventListener("click", (event) => {
      if (state.globalTagSuppressClick) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }
      onGlobalTagClick(segment);
    });
    button.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      removeGlobalTagDragGhost();
      state.globalTagPointerDrag = {
        segment,
        startX: event.clientX,
        startY: event.clientY,
        source: button,
      };
    });
    button.addEventListener("mousedown", (event) => {
      if (event.button !== 0) return;
      removeGlobalTagDragGhost();
      state.globalTagPointerDrag = {
        segment,
        startX: event.clientX,
        startY: event.clientY,
        source: button,
      };
    });
    button.addEventListener("dragstart", (event) => {
      state.globalTagDragging = segment;
      button.classList.add("dragging");
      event.dataTransfer?.setData(GLOBAL_TAG_DRAG_TYPE, segment);
      event.dataTransfer?.setData("text/plain", segment);
      if (event.dataTransfer) event.dataTransfer.effectAllowed = "copy";
    });
    button.addEventListener("dragend", () => {
      state.globalTagDragging = "";
      button.classList.remove("dragging");
      refs.captionEditor?.classList.remove("drag-over");
      removeGlobalTagDragGhost();
    });
    return button;
  }

  function scheduleGlobalTagViewportRender() {
    if (globalTagScrollFrame) return;
    globalTagScrollFrame = window.requestAnimationFrame(() => {
      globalTagScrollFrame = 0;
      renderGlobalTagViewport();
    });
  }

  function renderGlobalTagViewport() {
    const rows = Array.isArray(state.globalTagVirtualRows) ? state.globalTagVirtualRows : [];
    const list = refs.globalTagList;
    if (!list) return;
    const rowStep = GLOBAL_TAG_ROW_HEIGHT + GLOBAL_TAG_ROW_GAP;
    const viewportHeight = list.clientHeight || 480;
    const overscan = globalTagScrolling ? GLOBAL_TAG_SCROLL_OVERSCAN : GLOBAL_TAG_IDLE_OVERSCAN;
    const start = Math.max(0, Math.floor(list.scrollTop / rowStep) - overscan);
    const end = Math.min(rows.length, Math.ceil((list.scrollTop + viewportHeight) / rowStep) + overscan);
    const active = state.segmentQuery.toLowerCase();
    const signature = `${start}:${end}:${rows.length}:${active}:${globalTagScrolling ? "scroll" : "idle"}`;
    if (signature === globalTagViewportSignature) return;
    globalTagViewportSignature = signature;

    const canvas = document.createElement("div");
    canvas.className = "global-tag-virtual-canvas";
    canvas.style.height = `${rows.length * rowStep}px`;

    const fragment = document.createDocumentFragment();
    rows.slice(start, end).forEach((row, offset) => {
      const item = createGlobalTagRow(row);
      item.style.transform = `translate3d(0, ${(start + offset) * rowStep}px, 0)`;
      fragment.appendChild(item);
    });
    canvas.appendChild(fragment);
    list.replaceChildren(canvas);
  }

  function setGlobalTagsEmpty(text) {
    if (globalTagScrollEndTimer) {
      window.clearTimeout(globalTagScrollEndTimer);
      globalTagScrollEndTimer = 0;
    }
    globalTagScrolling = false;
    const empty = document.createElement("div");
    empty.className = "global-tag-empty";
    empty.textContent = text;
    refs.globalTagList.replaceChildren(empty);
  }

  function resetGlobalTagSearchState(query, rows) {
    if (refs.globalTagSearch) {
      refs.globalTagSearch.disabled = false;
      refs.globalTagSearch.placeholder = `搜索全局短语，共${state.globalSegments.length}项`;
      refs.globalTagSearch.title = query ? `匹配 ${rows.length} / 共 ${state.globalSegments.length} 项` : `共 ${state.globalSegments.length} 项`;
    }
    if (refs.globalTagCount) refs.globalTagCount.textContent = query ? `${rows.length}/${state.globalSegments.length}` : `${state.globalSegments.length}`;
  }

  function renderGlobalTags() {
    const query = normalizeGlobalTagQuery();
    const rows = state.globalSegments.filter((row) => {
      const segment = `${row.segment || row.tag || ""}`;
      return !query || segment.toLowerCase().includes(query);
    });
    const previousQuery = state.globalTagVirtualQuery || "";
    state.globalTagVirtualQuery = query;
    state.globalTagVirtualRows = rows;
    if (globalTagScrollEndTimer) {
      window.clearTimeout(globalTagScrollEndTimer);
      globalTagScrollEndTimer = 0;
    }
    globalTagScrolling = false;
    globalTagViewportSignature = "";
    resetGlobalTagSearchState(query, rows);
    refs.globalTagList.classList.toggle("virtualized", rows.length > 0);
    if (!rows.length) {
      setGlobalTagsEmpty(query ? "没有匹配的全局短语。" : "暂无全局短语。");
      return;
    }
    if (previousQuery !== query) {
      refs.globalTagList.scrollTop = 0;
    }
    renderGlobalTagViewport();
  }

  function clearCaptionAutosaveTimer() {
    if (!state.captionAutoSaveTimer) return;
    window.clearTimeout(state.captionAutoSaveTimer);
    state.captionAutoSaveTimer = 0;
  }

  async function saveCaptionSnapshot(name, text, { refresh = false, preserveEditor = true } = {}) {
    if (!name) return true;
    const savedText = normalizeCaptionInputText(text);
    const data = await apiPost("/api/item/save", {
      name,
      text: savedText,
    });
    if (name === state.selectedName) {
      state.currentItem = data.item;
      state.captionSavedText = savedText;
      state.captionDirty = state.currentText !== state.captionSavedText;
      if (!preserveEditor) {
        setCaptionEditorText(data.item.text || "", { markSaved: true });
      }
      if (refs.translatedText && !state.captionDirty) refs.translatedText.value = "";
    }
    if (refresh) {
      await refreshItems({ skipDirtyCheck: true, suppressSelectionSync: true });
    }
    return true;
  }

  function scheduleCaptionAutosave(delay = 700) {
    clearCaptionAutosaveTimer();
    if (!state.selectedName || !state.captionDirty) return;
    const name = state.selectedName;
    const text = state.currentText;
    state.captionAutoSaveTimer = window.setTimeout(() => {
      state.captionAutoSaveTimer = 0;
      state.captionAutoSavePromise = saveCaptionSnapshot(name, text, { preserveEditor: true })
        .catch((error) => {
          state.captionDirty = true;
          setAiStatusLine(`自动保存 Caption 失败：${error.message || error}`);
          return false;
        });
    }, delay);
  }

  async function flushCaptionAutosave() {
    clearCaptionAutosaveTimer();
    if (state.captionAutoSavePromise) {
      await state.captionAutoSavePromise;
      state.captionAutoSavePromise = null;
    }
    if (!state.selectedName || !state.captionDirty) return true;
    try {
      return await saveCaptionSnapshot(state.selectedName, state.currentText, { preserveEditor: true });
    } catch (error) {
      state.captionDirty = true;
      setAiStatusLine(`自动保存 Caption 失败：${error.message || error}`);
      return false;
    }
  }

  async function saveCurrentCaption() {
    if (!state.selectedName) return true;
    clearCaptionAutosaveTimer();
    if (state.captionAutoSavePromise) {
      await state.captionAutoSavePromise;
      state.captionAutoSavePromise = null;
    }
    if (!state.captionDirty) return true;
    try {
      return await saveCaptionSnapshot(state.selectedName, state.currentText, { refresh: true, preserveEditor: true });
    } catch (error) {
      state.captionDirty = true;
      throw error;
    }
  }

  async function translateCurrent() {
    if (!state.currentItem) return;
    const text = state.currentText || state.currentItem.text || "";
    if (!text.trim()) return;
    const data = await apiPost("/api/translate", { text });
    refs.translatedText.value = data.translated;
  }

  async function batchAdd(position = "after") {
    const segments = splitSegmentInput(refs.batchAddInput.value);
    if (!segments.length) {
      setAiStatusLine("请输入要批量添加的短语。");
      return;
    }
    const normalizedPosition = position === "before" ? "before" : "after";
    await apiPost("/api/batch/add-segments", { names: visibleNames(), segments, position: normalizedPosition });
    refs.batchAddInput.value = "";
    await refreshItems();
    setAiStatusLine(`批量添加至${normalizedPosition === "before" ? "最前" : "最后"}完成：${segments.length} 个短语`);
  }

  async function batchDelete() {
    const segments = splitSegmentInput(refs.batchDeleteInput.value);
    if (!segments.length) {
      setAiStatusLine("请输入要批量删除的短语。");
      return;
    }
    await apiPost("/api/batch/delete-segments", { names: visibleNames(), segments });
    refs.batchDeleteInput.value = "";
    await refreshItems();
    setAiStatusLine(`批量删除完成：${segments.length} 个短语`);
  }

  async function batchReplace() {
    const oldSegment = refs.batchReplaceOld.value.trim();
    if (!oldSegment) {
      setAiStatusLine("请输入要批量替换的旧短语。");
      return;
    }
    await apiPost("/api/batch/replace-segment", {
      names: visibleNames(),
      old_segment: oldSegment,
      new_segment: refs.batchReplaceNew.value.trim(),
    });
    refs.batchReplaceOld.value = "";
    refs.batchReplaceNew.value = "";
    await refreshItems();
    setAiStatusLine(`批量替换完成：${oldSegment}`);
  }

  async function batchRename(operation) {
    if (!(await confirmDiscardCaptionChanges())) return;
    const payload = { names: visibleNames(), operation };
    if (operation === "add_prefix" || operation === "add_suffix") {
      const value = refs.batchRenameAddInput.value.trim();
      if (!value) {
        setAiStatusLine("请输入要添加到文件名的文字。");
        return;
      }
      payload.value = value;
    } else if (operation === "delete") {
      const value = refs.batchRenameDeleteInput.value.trim();
      if (!value) {
        setAiStatusLine("请输入要从文件名删除的文字。");
        return;
      }
      payload.value = value;
    } else if (operation === "replace") {
      const oldValue = refs.batchRenameReplaceOld.value.trim();
      if (!oldValue) {
        setAiStatusLine("请输入要批量替换的旧文件名文字。");
        return;
      }
      payload.old_value = oldValue;
      payload.new_value = refs.batchRenameReplaceNew.value.trim();
    }

    const data = await apiPost("/api/batch/rename", payload);
    if (data.workspace) applyWorkspaceSummary(data.workspace);
    if (operation === "add_prefix" || operation === "add_suffix") refs.batchRenameAddInput.value = "";
    if (operation === "delete") refs.batchRenameDeleteInput.value = "";
    if (operation === "replace") {
      refs.batchRenameReplaceOld.value = "";
      refs.batchRenameReplaceNew.value = "";
    }
    await refreshItems({ skipDirtyCheck: true, suppressSelectionSync: true });
    setAiStatusLine(`批量重命名完成：${data.changed || 0} 项`);
  }

  async function swapControlResultPairs() {
    if (!(await confirmDiscardCaptionChanges())) return;
    const controlDir = refs.swapControlDir?.value.trim() || "";
    const resultDir = refs.swapResultDir?.value.trim() || "";
    const suffix = refs.swapSuffix?.value.trim() || "_swap";
    if (!controlDir || !resultDir) {
      setAiStatusLine("请先填写控制图目录和结果图目录。");
      return;
    }
    const ok = await window.appConfirm("将按同名图片生成对调副本：结果图复制到控制图目录，控制图复制到结果图目录。原始文件不会被修改。");
    if (!ok) return;
    setAiStatusLine("正在生成对调副本...");
    const data = await apiPost("/api/batch/swap-control-result", {
      control_dir: controlDir,
      result_dir: resultDir,
      suffix,
    });
    if (data.workspace) applyWorkspaceSummary(data.workspace);
    await refreshItems({ skipDirtyCheck: true });
    const skipped = Array.isArray(data.skipped) && data.skipped.length ? ` · 跳过 ${data.skipped.length} 项` : "";
    setAiStatusLine(`对调扩增完成：${data.swapped || 0} 对${skipped}`);
  }

  async function deleteCurrent() {
    if (!state.selectedName) return;
    if (!(await confirmDiscardCaptionChanges())) return;
    const ok = await window.appConfirm(`确定从导出数据集中排除 ${state.selectedName}？原始文件不会被删除。`);
    if (!ok) return;
    await apiPost("/api/item/delete", { name: state.selectedName });
    await refreshItems();
  }

  async function loadPromptTemplates() {
    const data = await apiGet("/api/prompt-templates");
    state.promptTemplates = data.templates || [];
    renderPromptTemplateSelectors();
  }

  async function savePromptTemplateFor(targetId) {
    const textarea = document.querySelector(`#${targetId}`);
    if (!textarea) return;
    const name = await window.appPrompt("模板名称", selectedTemplateNameFor(targetId));
    if (!name) return;
    const data = await apiPost("/api/prompt-templates/save", {
      name,
      content: textarea.value,
    });
    state.promptTemplates = data.templates || [];
    renderPromptTemplateSelectors();
    setAiStatusLine(`模板已保存：${name}`);
  }

  async function deletePromptTemplate(templateId) {
    if (!templateId) return;
    const data = await apiPost("/api/prompt-templates/delete", { id: templateId });
    state.promptTemplates = data.templates || [];
    renderPromptTemplateSelectors();
    setAiStatusLine("模板已删除");
  }

  return {
    renderPromptTemplateSelectors,
    templateById,
    renderTags,
    appendSegmentsToCaption,
    toggleQuickTags,
    renderQuickTags,
    renderGlobalTags,
    saveCurrentCaption,
    scheduleCaptionAutosave,
    flushCaptionAutosave,
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
  };
}
