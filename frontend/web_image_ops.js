export function createImageOpsModule({
  state,
  refs,
  apiPost,
  apiPostDownload,
  pollAiStatus,
  renderViewer,
  refreshItems,
}) {
  function renderImageProcessStatus(process) {
    if (!refs.processStatus || !refs.processProgressBar) return;
    if (!process || process.status === "idle") {
      refs.processStatus.textContent = "等待图像处理";
      refs.processProgressBar.style.width = "0%";
      refs.processImagesBtn.disabled = false;
      if (refs.processMatchResultBtn) refs.processMatchResultBtn.disabled = false;
      return;
    }

    const pct = Math.max(0, Math.min(Number(process.progress_pct || 0), 100));
    refs.processProgressBar.style.width = `${pct}%`;
    refs.processImagesBtn.disabled = Boolean(process.running);
    if (refs.processMatchResultBtn) refs.processMatchResultBtn.disabled = Boolean(process.running);
    const processMode = process.mode === "match_result" ? "match_result" : "process";
    const modeLabel = processMode === "match_result" ? "匹配结果尺寸" : "图像处理";

    if (process.running) {
      refs.processStatus.textContent = `${modeLabel}中 ${process.done || 0}/${process.total || 0}${process.current ? ` · ${process.current}` : ""}`;
      return;
    }
    if (process.status === "done") {
      const result = process.result || {};
      const loadNote = process.workspace_loaded ? "已加载为当前工作区" : "未切换当前工作区";
      refs.processStatus.textContent = `${modeLabel}完成：${process.processed || 0} 项 · ${loadNote} · ${result.path || ""}`;
      return;
    }
    if (process.status === "error") {
      refs.processStatus.textContent = `${modeLabel}失败，查看启动终端输出。`;
      return;
    }
    refs.processStatus.textContent = `${process.status || "处理中"} ${process.done || 0}/${process.total || 0}`;
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
    refs.processStatus.textContent = "正在启动图像处理任务...";
    refs.processProgressBar.style.width = "0%";
    await apiPost("/api/images/process/start", imageProcessPayload());
    state.lastImageProcessSignature = "";
    await pollAiStatus({ scheduleNext: true });
  }

  async function processMatchResultSizes() {
    refs.processStatus.textContent = "正在启动批量匹配结果尺寸...";
    refs.processProgressBar.style.width = "0%";
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
    refs.viewerProcessStatus.textContent = "正在缩放当前条目图像...";
    const data = await apiPost("/api/images/item/scale", {
      name: state.selectedName,
      target_megapixels: target,
    });
    state.currentItem = data.item;
    refs.viewerProcessStatus.textContent = `已缩放当前条目 · 目标 ${target} 百万像素 · 16 倍数`;
    renderViewer();
    await refreshItems({ skipDirtyCheck: true, suppressSelectionSync: true });
  }

  async function matchViewerControlsToResult() {
    if (!state.selectedName) return;
    refs.viewerProcessStatus.textContent = "正在匹配控制图到结果图尺寸...";
    const data = await apiPost("/api/images/item/match-result", {
      name: state.selectedName,
    });
    state.currentItem = data.item;
    const size = data.process?.target_size;
    refs.viewerProcessStatus.textContent = Array.isArray(size)
      ? `控制图已匹配结果图尺寸：${size[0]}×${size[1]}`
      : "控制图已匹配结果图尺寸";
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
    };
  }

  async function exportDataset() {
    refs.exportStatus.textContent = "正在导出数据集...";
    const result = await apiPostDownload("/api/export/dataset", exportPayload());
    if (result.type === "blob") {
      const url = URL.createObjectURL(result.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      refs.exportStatus.textContent = `ZIP 已生成并开始下载：${result.filename}`;
      return;
    }
    const exportInfo = result.data.export || {};
    refs.exportStatus.textContent = `文件夹导出完成：${exportInfo.path || ""} · ${exportInfo.exported || 0} 项`;
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
