export function createShellModule({
  state,
  refs,
  UTILITY_PANEL_LABELS,
  STORAGE_KEYS,
  saveStored,
  readStored,
  getLocalCaptionPayload,
  getApiCaptionPayload,
  getOllamaCaptionPayload,
}) {
  function utilityPanelExists(panel) {
    return document.querySelector(`.utility-panel[data-panel="${panel}"]`);
  }

  function renderUtilityPanelState() {
    const panel = utilityPanelExists(state.utilityPanel) ? state.utilityPanel : "workspace";
    state.utilityPanel = panel;
    refs.utilityPageShell?.setAttribute("aria-hidden", state.utilityOpen ? "false" : "true");
    refs.workbenchShell?.classList.toggle("page-open", state.utilityOpen);
    if (refs.utilityPageTitle) {
      refs.utilityPageTitle.textContent = UTILITY_PANEL_LABELS[panel] || "配置";
    }
    refs.utilityActions?.querySelectorAll("button[data-panel]").forEach((button) => {
      const isCurrent = button.dataset.panel === panel;
      button.classList.toggle("active", state.utilityOpen && isCurrent);
      button.setAttribute("aria-expanded", String(state.utilityOpen && isCurrent));
    });
    document.querySelectorAll(".utility-panel").forEach((node) => {
      node.classList.toggle("active", node.dataset.panel === panel);
    });
  }

  function setUtilityPanel(panel, { open = true, persist = true } = {}) {
    state.utilityPanel = utilityPanelExists(panel) ? panel : "workspace";
    state.utilityOpen = Boolean(open);
    renderUtilityPanelState();
    if (state.utilityOpen && refs.utilityPageShell) {
      refs.utilityPageShell.scrollTop = 0;
    }
    if (persist) saveStored(STORAGE_KEYS.utilityPanel, state.utilityPanel);
  }

  function closeUtilityPanel() {
    state.utilityOpen = false;
    renderUtilityPanelState();
  }

  function setAiStatusLine(message) {
    refs.aiStatusLine.textContent = message || "待命";
  }

  async function runWithStatus(message, task) {
    setAiStatusLine(message);
    return await task();
  }

  function activeCaptionBackend() {
    return refs.captionBackend?.value || readStored(STORAGE_KEYS.captionBackend, "local");
  }

  function activeCaptionBackendLabel() {
    return {
      local: "本地 Qwen",
      api: "OpenAI 兼容 API",
      ollama: "Ollama",
    }[activeCaptionBackend()] || "本地 Qwen";
  }

  function activeCaptionPayload() {
    const backend = activeCaptionBackend();
    if (backend === "api") return getApiCaptionPayload();
    if (backend === "ollama") return getOllamaCaptionPayload();
    return getLocalCaptionPayload();
  }

  return {
    renderUtilityPanelState,
    setUtilityPanel,
    closeUtilityPanel,
    setAiStatusLine,
    runWithStatus,
    activeCaptionBackend,
    activeCaptionBackendLabel,
    activeCaptionPayload,
  };
}
