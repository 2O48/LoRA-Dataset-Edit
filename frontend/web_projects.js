export function createProjectsModule({
  state,
  refs,
  apiGet,
  apiPost,
  runWithStatus,
  showError,
  applyWorkspaceSummary,
  refreshItems,
  closeUtilityPanel,
}) {
  function projectProgressText(project) {
    const total = Number(project.item_count || 0);
    const done = Number(project.captioned_count || 0);
    if (!total) return "0 项";
    return `${done}/${total} 已标注`;
  }

  function visibleProjects() {
    const query = state.projectQuery.trim().toLowerCase();
    let rows = state.projects.filter((project) => {
      if (!query) return true;
      return `${project.name || ""} ${project.id || ""}`.toLowerCase().includes(query);
    });
    rows = [...rows].sort((a, b) => {
      if (state.projectSortMode === "name") {
        return `${a.name || ""}`.localeCompare(`${b.name || ""}`, "zh-CN");
      }
      const key = state.projectSortMode === "created" ? "created_at" : "updated_at";
      return `${b[key] || ""}`.localeCompare(`${a[key] || ""}`);
    });
    return rows;
  }

  async function refreshProjects() {
    const data = await apiGet("/api/projects");
    state.projects = data.projects || [];
    renderProjects();
    if (refs.projectStatus) {
      refs.projectStatus.textContent = `已载入 ${state.projects.length} 个项目`;
    }
  }

  async function saveCurrentProject() {
    const fallback = refs.exportProjectName?.value.trim() || refs.processProjectName?.value.trim() || "未命名项目";
    const name = refs.projectNameInput.value.trim() || fallback;
    const data = await apiPost("/api/projects/save", { name });
    refs.projectNameInput.value = data.project?.name || name;
    refs.projectStatus.textContent = `已保存项目：${data.project?.name || name}`;
    await refreshProjects();
  }

  async function openProject(projectId) {
    const data = await apiPost("/api/projects/open", { id: projectId });
    applyWorkspaceSummary(data.workspace);
    await refreshItems({ skipDirtyCheck: true });
    refs.projectStatus.textContent = `已打开项目：${data.project?.name || projectId}`;
    closeUtilityPanel();
  }

  async function renameProject(project) {
    const name = window.prompt("输入新的项目名称", project.name || project.id);
    if (!name || !name.trim()) return;
    await runWithStatus("正在重命名项目...", async () => {
      const data = await apiPost("/api/projects/rename", { id: project.id, name: name.trim() });
      refs.projectStatus.textContent = `已重命名项目：${data.project?.name || name.trim()}`;
      await refreshProjects();
    }).catch(showError);
  }

  async function deleteProject(project) {
    if (!window.confirm(`删除项目「${project.name || project.id}」？该操作会删除 datasets/projects 下的项目文件。`)) return;
    await runWithStatus("正在删除项目...", async () => {
      await apiPost("/api/projects/delete", { id: project.id });
      refs.projectStatus.textContent = `已删除项目：${project.name || project.id}`;
      await refreshProjects();
    }).catch(showError);
  }

  async function cleanupTmpNow() {
    const data = await apiPost("/api/tmp/cleanup", { max_age_hours: 48 });
    const cleanup = data.cleanup || {};
    refs.projectStatus.textContent = `tmp 清理完成：删除 ${cleanup.removed?.length || 0} 项，跳过 ${cleanup.skipped?.length || 0} 项`;
  }

  function renderProjects() {
    if (!refs.projectGrid) return;
    refs.projectGrid.textContent = "";
    const rows = visibleProjects();
    if (!rows.length) {
      const empty = document.createElement("div");
      empty.className = "project-empty";
      empty.textContent = state.projects.length ? "没有匹配的项目" : "暂无已保存项目";
      refs.projectGrid.appendChild(empty);
      return;
    }

    for (const project of rows) {
      const card = document.createElement("article");
      card.className = "project-card";
      const thumb = document.createElement("div");
      thumb.className = "project-thumb";
      if (project.thumbnail) {
        const img = document.createElement("img");
        img.loading = "lazy";
        img.src = `/api/projects/thumbnail?id=${encodeURIComponent(project.id)}&width=520&height=320`;
        img.alt = project.name || project.id;
        thumb.appendChild(img);
      } else {
        thumb.textContent = "No Preview";
      }

      const body = document.createElement("div");
      body.className = "project-card-body";
      const title = document.createElement("h3");
      title.textContent = project.name || project.id;
      const meta = document.createElement("p");
      meta.textContent = `${projectProgressText(project)} · ${project.updated_at || "未记录时间"}`;
      const actions = document.createElement("div");
      actions.className = "project-actions";

      const openBtn = document.createElement("button");
      openBtn.className = "button-primary";
      openBtn.type = "button";
      openBtn.textContent = "打开";
      openBtn.addEventListener("click", () => runWithStatus("正在打开项目...", () => openProject(project.id)).catch(showError));

      const renameBtn = document.createElement("button");
      renameBtn.className = "button-ghost";
      renameBtn.type = "button";
      renameBtn.textContent = "重命名";
      renameBtn.addEventListener("click", () => renameProject(project));

      const deleteBtn = document.createElement("button");
      deleteBtn.className = "button-ghost danger";
      deleteBtn.type = "button";
      deleteBtn.textContent = "删除";
      deleteBtn.addEventListener("click", () => deleteProject(project));

      actions.append(openBtn, renameBtn, deleteBtn);
      body.append(title, meta, actions);
      card.append(thumb, body);
      refs.projectGrid.appendChild(card);
    }
  }

  return {
    renderProjects,
    refreshProjects,
    saveCurrentProject,
    openProject,
    renameProject,
    deleteProject,
    cleanupTmpNow,
  };
}
