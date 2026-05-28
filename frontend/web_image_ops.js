export function createImageOpsModule({
  state,
  refs,
  apiPost,
  pollAiStatus,
  renderViewer,
  refreshItems,
  setAiStatusLine,
}) {
  function refreshViewerImages() {
    state.workspaceImageVersion = (state.workspaceImageVersion || 0) + 1;
    state.imageRefreshToken = `${Date.now()}-${state.workspaceImageVersion}-${state.workspace?.workspace_key || ""}`;
  }

  function renderImageProcessStatus(process) {
    if (!process || process.status === "idle") {
      refs.processImagesBtn.disabled = false;
      if (refs.processMatchResultBtn) refs.processMatchResultBtn.disabled = false;
      return;
    }

    const pct = Math.max(0, Math.min(Number(process.progress_pct || 0), 100));
    if (refs.topAiProgressBar) refs.topAiProgressBar.style.width = `${pct}%`;
    refs.processImagesBtn.disabled = Boolean(process.running);
    if (refs.processMatchResultBtn) refs.processMatchResultBtn.disabled = Boolean(process.running);
    const processMode = process.mode === "match_result" ? "match_result" : "process";
    const modeLabel = processMode === "match_result" ? "匹配结果尺寸" : "图像处理";

    if (process.running) {
      setAiStatusLine(`${modeLabel}中 ${process.done || 0}/${process.total || 0}${process.current ? ` · ${process.current}` : ""}`);
      return;
    }
    if (process.status === "done") {
      const result = process.result || {};
      const loadNote = process.workspace_loaded ? "已加载为当前工作区" : "未切换当前工作区";
      setAiStatusLine(`${modeLabel}完成：${process.processed || 0} 项 · ${loadNote} · ${result.path || ""}`);
      return;
    }
    if (process.status === "error") {
      setAiStatusLine(`${modeLabel}失败，查看启动终端输出。`);
      return;
    }
    setAiStatusLine(`${process.status || "处理中"} ${process.done || 0}/${process.total || 0}`);
  }

  function imageProcessPayload() {
    return {
      output_dir: "",
      project_name: refs.processProjectName.value.trim() || refs.exportProjectName.value.trim(),
      target_megapixels: Number(refs.exportTargetPixels.value || 4),
      multiple: Number(refs.exportSizeMultiple.value || 16),
      include_controls: refs.processIncludeControls.checked,
      load_workspace: refs.processLoadWorkspace.checked,
    };
  }

  async function processImages() {
    setAiStatusLine("正在启动图像处理任务...");
    if (refs.topAiProgressBar) refs.topAiProgressBar.style.width = "0%";
    await apiPost("/api/images/process/start", imageProcessPayload());
    state.lastImageProcessSignature = "";
    await pollAiStatus({ scheduleNext: true });
  }

  async function processMatchResultSizes() {
    setAiStatusLine("正在启动批量匹配结果尺寸...");
    if (refs.topAiProgressBar) refs.topAiProgressBar.style.width = "0%";
    await apiPost("/api/images/match-result/start", {
      output_dir: "",
      project_name: refs.processProjectName.value.trim() || refs.exportProjectName.value.trim(),
      include_controls: refs.processIncludeControls.checked,
      load_workspace: refs.processLoadWorkspace.checked,
      only_mismatched: refs.processOnlyMismatched.checked,
    });
    state.lastImageProcessSignature = "";
    await pollAiStatus({ scheduleNext: true });
  }

  async function scaleViewerItem() {
    if (!state.selectedName) return;
    const target = Number(refs.viewerTargetPixels.value || 4);
    setAiStatusLine("正在缩放当前条目图像...");
    const data = await apiPost("/api/images/item/scale", {
      name: state.selectedName,
      target_megapixels: target,
    });
    state.currentItem = data.item;
    refreshViewerImages();
    setAiStatusLine(`已缩放当前条目 · 目标 ${target} 百万像素 · 16 倍数`);
    renderViewer();
    await refreshItems({ skipDirtyCheck: true, suppressSelectionSync: true });
  }

  async function matchViewerControlsToResult() {
    if (!state.selectedName) return;
    setAiStatusLine("正在匹配控制图到结果图尺寸...");
    const data = await apiPost("/api/images/item/match-result", {
      name: state.selectedName,
    });
    state.currentItem = data.item;
    refreshViewerImages();
    const size = data.process?.target_size;
    setAiStatusLine(Array.isArray(size)
      ? `控制图已匹配结果图尺寸：${size[0]}×${size[1]}`
      : "控制图已匹配结果图尺寸");
    renderViewer();
    await refreshItems({ skipDirtyCheck: true, suppressSelectionSync: true });
  }

  function exportPayload() {
    return {
      format: refs.exportFormat.value,
      output_dir: refs.exportOutputDir.value.trim(),
      project_name: refs.exportProjectName.value.trim(),
      target_megapixels: Number(refs.exportTargetPixels.value || 4),
      multiple: Number(refs.exportSizeMultiple.value || 16),
      process_images: refs.exportProcessImages.checked,
      include_controls: refs.exportIncludeControls.checked,
      preserve_subfolders: refs.exportPreserveSubfolders.checked,
    };
  }

  async function exportDataset() {
    setAiStatusLine("正在导出数据集...");
    if (refs.topAiProgressBar) refs.topAiProgressBar.style.width = "0%";
    state.exportDownloadRequested = true;
    state.lastExportSignature = "";
    state.lastExportDownloadPath = "";
    await apiPost("/api/export/start", exportPayload());
    await pollAiStatus({ scheduleNext: true });
  }

  return {
    renderImageProcessStatus,
    processImages,
    processMatchResultSizes,
    scaleViewerItem,
    matchViewerControlsToResult,
    exportDataset,
  };
}
