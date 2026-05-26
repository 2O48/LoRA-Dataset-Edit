export function createWorkspaceBrowserModule({
  state,
  refs,
  ROLE_LABELS,
  STORAGE_KEYS,
  saveStored,
  apiGet,
  showError,
  activeControlCount,
}) {
  function workspaceDirRef(target) {
    return {
      control1: refs.control1Dir,
      control2: refs.control2Dir,
      control3: refs.control3Dir,
      result: refs.resultDir,
    }[target] || refs.control1Dir;
  }

  function workspaceBrowserTargetLabel(target = state.browserTarget) {
    return ROLE_LABELS[target] || "目录";
  }

  function syncWorkspaceBrowserTargetVisibility() {
    const count = activeControlCount();
    refs.workspaceBrowserTargetGroup.querySelectorAll("button[data-browser-target]").forEach((button) => {
      const target = button.dataset.browserTarget;
      const shouldHide =
        (target === "control1" && count < 1) ||
        (target === "control2" && count < 2) ||
        (target === "control3" && count < 3);
      button.style.display = shouldHide ? "none" : "";
    });
    if (
      (state.browserTarget === "control1" && count < 1) ||
      (state.browserTarget === "control2" && count < 2) ||
      (state.browserTarget === "control3" && count < 3)
    ) {
      state.browserTarget = "result";
      saveStored(STORAGE_KEYS.workspaceBrowserTarget, state.browserTarget);
    }
  }

  function renderWorkspaceBrowser() {
    syncWorkspaceBrowserTargetVisibility();
    refs.workspaceBrowserTargetGroup.querySelectorAll("button[data-browser-target]").forEach((button) => {
      button.classList.toggle("active", button.dataset.browserTarget === state.browserTarget);
    });

    const pathText = state.browserPath || refs.workspaceBrowserRoot.value.trim() || "未选择目录";
    refs.workspaceBrowserPath.textContent = state.browserMessage
      ? `${state.browserMessage} · ${pathText}`
      : pathText;
    refs.workspaceBrowserList.textContent = "";

    if (!state.browserPath) {
      const empty = document.createElement("div");
      empty.className = "folder-browser-empty";
      empty.textContent = "输入父目录后点击浏览子目录。";
      refs.workspaceBrowserList.appendChild(empty);
      return;
    }

    if (!state.browserItems.length) {
      const empty = document.createElement("div");
      empty.className = "folder-browser-empty";
      empty.textContent = "当前目录没有可选子目录，可直接使用当前目录。";
      refs.workspaceBrowserList.appendChild(empty);
      return;
    }

    for (const item of state.browserItems) {
      const row = document.createElement("div");
      row.className = "folder-row";

      const openButton = document.createElement("button");
      openButton.type = "button";
      openButton.className = "folder-open-btn";
      const title = document.createElement("span");
      title.className = "folder-name";
      title.textContent = item.name;
      const meta = document.createElement("span");
      meta.className = "folder-meta";
      meta.textContent = `${item.image_count || 0} 张图片 · 点击进入`;
      openButton.appendChild(title);
      openButton.appendChild(meta);
      openButton.addEventListener("click", () => {
        browseWorkspacePath(item.path).catch(showError);
      });

      const selectButton = document.createElement("button");
      selectButton.type = "button";
      selectButton.className = "button-ghost folder-select-btn";
      selectButton.textContent = `填入${workspaceBrowserTargetLabel()}`;
      selectButton.addEventListener("click", () => applyWorkspaceBrowserPath(item.path));

      row.appendChild(openButton);
      row.appendChild(selectButton);
      refs.workspaceBrowserList.appendChild(row);
    }
  }

  function setWorkspaceBrowserTarget(target) {
    if (!workspaceDirRef(target)) return;
    state.browserTarget = target;
    saveStored(STORAGE_KEYS.workspaceBrowserTarget, target);
    const currentValue = workspaceDirRef(target)?.value?.trim() || "";
    if (!refs.workspaceBrowserRoot.value.trim() && currentValue) {
      refs.workspaceBrowserRoot.value = currentValue;
    }
    renderWorkspaceBrowser();
  }

  function seedWorkspaceBrowserRootFromInputs() {
    if (refs.workspaceBrowserRoot.value.trim()) return;
    const firstPath = [
      refs.resultDir.value,
      refs.control1Dir.value,
      refs.control2Dir.value,
      refs.control3Dir.value,
    ].find((value) => `${value || ""}`.trim());
    if (firstPath) {
      refs.workspaceBrowserRoot.value = firstPath.trim();
    }
  }

  function applyWorkspaceBrowserPath(pathValue) {
    const value = `${pathValue || state.browserPath || ""}`.trim();
    if (!value) return;
    const input = workspaceDirRef(state.browserTarget);
    if (!input) return;
    input.value = value;
    input.dispatchEvent(new Event("change"));
    state.browserMessage = `已填入${workspaceBrowserTargetLabel()}`;
    renderWorkspaceBrowser();
  }

  async function browseWorkspacePath(pathValue = "") {
    const nextPath = `${pathValue || refs.workspaceBrowserRoot.value || ""}`.trim();
    if (!nextPath) {
      state.browserPath = "";
      state.browserParent = "";
      state.browserItems = [];
      state.browserMessage = "请输入目录";
      renderWorkspaceBrowser();
      return;
    }
    state.browserMessage = "正在读取目录";
    renderWorkspaceBrowser();
    let data;
    try {
      data = await apiGet("/api/workspace/browse", { path: nextPath });
    } catch (error) {
      state.browserMessage = error.message || "目录读取失败";
      renderWorkspaceBrowser();
      throw error;
    }
    const browser = data.browser || {};
    state.browserPath = browser.path || nextPath;
    state.browserParent = browser.parent || "";
    state.browserItems = Array.isArray(browser.items) ? browser.items : [];
    state.browserMessage = "";
    refs.workspaceBrowserRoot.value = state.browserPath;
    saveStored(STORAGE_KEYS.workspaceBrowserRoot, state.browserPath);
    renderWorkspaceBrowser();
  }

  return {
    setWorkspaceBrowserTarget,
    seedWorkspaceBrowserRootFromInputs,
    syncWorkspaceBrowserTargetVisibility,
    applyWorkspaceBrowserPath,
    renderWorkspaceBrowser,
    browseWorkspacePath,
  };
}
