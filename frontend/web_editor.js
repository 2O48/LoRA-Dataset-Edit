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
  visibleNames,
  renderViewer,
  confirmDiscardCaptionChanges,
  setCaptionEditorText,
  syncSegmentsFromText,
  syncCaptionDirty,
  onGlobalTagClick,
}) {
  function renderPromptTemplateSelectors() {
    document.querySelectorAll(".promptTemplateSelect").forEach((select) => {
      const previous = select.value;
      select.innerHTML = state.promptTemplates
        .map((item) => `<option value="${item.id}">${item.name}</option>`)
        .join("");
      if (state.promptTemplates.some((item) => item.id === previous)) {
        select.value = previous;
      }
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
    state.currentText = segments.join(", ");
    if (refs.captionEditor) refs.captionEditor.value = state.currentText;
    syncSegmentsFromText();
    syncCaptionDirty();
  }

  function renderTags() {
    refs.tagChips.innerHTML = "";
    state.currentSegments.forEach((segment, index) => {
      const row = document.createElement("div");
      row.className = "chip";
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
    state.currentText += `${prefix}${additions.join(", ")}`;
    if (refs.captionEditor) refs.captionEditor.value = state.currentText;
    syncSegmentsFromText();
    syncCaptionDirty();
    renderTags();
  }

  function appendQuickTagToCaption(value) {
    const text = `${value ?? ""}`;
    if (!text) return;
    state.currentText = `${state.currentText || ""}${text}`;
    if (refs.captionEditor) refs.captionEditor.value = state.currentText;
    syncSegmentsFromText();
    syncCaptionDirty();
    renderTags();
  }

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

  function renderGlobalTags() {
    refs.globalTagCount.textContent = `${state.globalSegments.length}`;
    refs.globalTagList.textContent = "";
    for (const row of state.globalSegments.slice(0, 600)) {
      const segment = row.segment || row.tag || "";
      const button = document.createElement("button");
      button.type = "button";
      button.className = `global-tag-row${state.segmentQuery.toLowerCase() === segment.toLowerCase() ? " active" : ""}`;
      const name = document.createElement("span");
      name.textContent = segment;
      const count = document.createElement("span");
      count.textContent = `${row.count}`;
      button.appendChild(name);
      button.appendChild(count);
      button.addEventListener("click", () => onGlobalTagClick(segment));
      refs.globalTagList.appendChild(button);
    }
  }

  async function saveCurrentCaption() {
    if (!state.selectedName) return;
    const data = await apiPost("/api/item/save", {
      name: state.selectedName,
      text: state.currentText,
    });
    state.currentItem = data.item;
    setCaptionEditorText(data.item.text || "", { markSaved: true });
    refs.translatedText.value = "";
    await refreshItems();
  }

  async function translateCurrent() {
    if (!state.currentItem) return;
    const text = state.currentText || state.currentItem.text || "";
    if (!text.trim()) return;
    const data = await apiPost("/api/translate", { text });
    refs.translatedText.value = data.translated;
  }

  async function batchAdd() {
    const segments = splitSegmentInput(refs.batchAddInput.value);
    if (!segments.length) return;
    await apiPost("/api/batch/add-segments", { names: visibleNames(), segments });
    refs.batchAddInput.value = "";
    await refreshItems();
  }

  async function batchDelete() {
    const segments = splitSegmentInput(refs.batchDeleteInput.value);
    if (!segments.length) return;
    await apiPost("/api/batch/delete-segments", { names: visibleNames(), segments });
    refs.batchDeleteInput.value = "";
    await refreshItems();
  }

  async function batchReplace() {
    const oldSegment = refs.batchReplaceOld.value.trim();
    if (!oldSegment) return;
    await apiPost("/api/batch/replace-segment", {
      names: visibleNames(),
      old_segment: oldSegment,
      new_segment: refs.batchReplaceNew.value.trim(),
    });
    refs.batchReplaceOld.value = "";
    refs.batchReplaceNew.value = "";
    await refreshItems();
  }

  async function deleteCurrent() {
    if (!state.selectedName) return;
    if (!(await confirmDiscardCaptionChanges())) return;
    const ok = window.confirm(`确定从导出数据集中排除 ${state.selectedName}？原始文件不会被删除。`);
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
    const name = window.prompt("模板名称", selectedTemplateNameFor(targetId));
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
    translateCurrent,
    batchAdd,
    batchDelete,
    batchReplace,
    deleteCurrent,
    loadPromptTemplates,
    savePromptTemplateFor,
    deletePromptTemplate,
  };
}
