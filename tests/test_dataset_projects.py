import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from dataset_projects import ProjectStore
from dataset_workspace import DatasetWorkspace


class ProjectStoreTests(unittest.TestCase):
    def _make_workspace(self, root: Path) -> DatasetWorkspace:
        result_dir = root / "source" / "result"
        control_dir = root / "source" / "control1"
        (result_dir / "system").mkdir(parents=True)
        (control_dir / "system").mkdir(parents=True)
        Image.new("RGB", (32, 32), (20, 30, 40)).save(result_dir / "system" / "display_off.png")
        Image.new("RGB", (32, 32), (40, 30, 20)).save(result_dir / "system" / "display_on.png")
        Image.new("RGB", (32, 32), (60, 70, 80)).save(control_dir / "system" / "display_off.png")
        Image.new("RGB", (32, 32), (80, 70, 60)).save(control_dir / "system" / "display_on.png")

        workspace = DatasetWorkspace()
        workspace.open_dirs(
            control1_dir=str(control_dir),
            result_dir=str(result_dir),
            control_count=1,
        )
        workspace.save_text("system/display_off", "display is off")
        return workspace

    def test_save_overwrite_preserves_uncaptioned_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ProjectStore(root / "app" / "projects")
            workspace = self._make_workspace(root)

            saved = store.save_project(
                name="车机图标",
                workspace=workspace,
                ui_state={"caption_settings": {"backend": "ollama"}},
            )
            project_id = saved["project"]["id"]
            project_dir = Path(saved["workspace"]["dirs"]["result"]).parents[1]

            self.assertTrue((project_dir / "assets" / "result" / "system" / "display_off.png").exists())
            self.assertTrue((project_dir / "assets" / "result" / "system" / "display_on.png").exists())
            self.assertEqual(saved["project"]["item_count"], 2)
            self.assertEqual(saved["project"]["captioned_count"], 1)

            reopened = DatasetWorkspace()
            reopened.open_dirs(
                control1_dir=saved["workspace"]["dirs"]["control1"],
                result_dir=saved["workspace"]["dirs"]["result"],
                control_count=1,
            )
            reopened.save_text("system/display_off", "edited off caption")
            overwritten = store.save_project(
                name="车机图标",
                workspace=reopened,
                overwrite_id=project_id,
                ui_state={"caption_settings": {"backend": "api"}},
            )

            result_dir = Path(overwritten["workspace"]["dirs"]["result"])
            self.assertTrue((result_dir / "system" / "display_off.png").exists())
            self.assertTrue((result_dir / "system" / "display_on.png").exists())
            self.assertEqual(overwritten["project"]["id"], project_id)
            self.assertEqual(overwritten["project"]["item_count"], 2)
            self.assertEqual(overwritten["project"]["captioned_count"], 1)
            self.assertEqual(
                (result_dir / "system" / "display_off.txt").read_text(encoding="utf-8"),
                "edited off caption",
            )
            self.assertEqual(
                (result_dir.parents[1] / "state" / "caption_config.json").read_text(encoding="utf-8"),
                '{\n  "backend": "api"\n}',
            )

    def test_overwrite_save_keeps_project_directory_in_place_and_cleans_tmp_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ProjectStore(root / "app" / "projects")
            workspace = self._make_workspace(root)
            saved = store.save_project(name="车机图标", workspace=workspace)
            project_id = saved["project"]["id"]
            project_dir = root / "app" / "projects" / project_id
            stale_tmp = root / "app" / "projects" / f".tmp-{project_id}-stale"
            stale_tmp.mkdir()
            (stale_tmp / "old.txt").write_text("old", encoding="utf-8")

            original_replace = Path.replace

            def guarded_replace(path, target):
                if Path(path).resolve() == project_dir.resolve():
                    raise AssertionError("overwrite save should not rename the open project directory")
                return original_replace(path, target)

            reopened = DatasetWorkspace()
            reopened.open_dirs(
                control1_dir=saved["workspace"]["dirs"]["control1"],
                result_dir=saved["workspace"]["dirs"]["result"],
                control_count=1,
            )
            reopened.save_text("system/display_off", "second caption")
            reopened.delete_item("system/display_on")

            with mock.patch.object(Path, "replace", guarded_replace):
                overwritten = store.save_project(
                    name="车机图标",
                    workspace=reopened,
                    overwrite_id=project_id,
                )

            self.assertEqual(overwritten["project"]["id"], project_id)
            self.assertEqual(overwritten["project"]["item_count"], 1)
            self.assertTrue(project_dir.is_dir())
            self.assertFalse(stale_tmp.exists())
            self.assertFalse(list((root / "app" / "projects").glob(f".tmp-{project_id}-*")))
            self.assertFalse((project_dir / "assets" / "result" / "system" / "display_on.png").exists())
            self.assertEqual(
                (project_dir / "assets" / "result" / "system" / "display_off.txt").read_text(encoding="utf-8"),
                "second caption",
            )

    def test_rename_clone_and_delete_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ProjectStore(root / "app" / "projects")
            workspace = self._make_workspace(root)
            saved = store.save_project(name="原项目", workspace=workspace)
            project_id = saved["project"]["id"]

            renamed = store.rename_project(project_id, "新项目")
            self.assertEqual(renamed["name"], "新项目")
            self.assertNotEqual(renamed["id"], project_id)
            self.assertTrue((root / "app" / "projects" / renamed["id"]).is_dir())
            renamed_detail = store.get_project(renamed["id"])
            self.assertIn(renamed["id"], renamed_detail["workspace"]["dirs"]["result"])

            cloned = store.clone_project(renamed["id"], "新项目副本")
            self.assertEqual(cloned["project"]["name"], "新项目副本")
            self.assertNotEqual(cloned["project"]["id"], renamed["id"])
            self.assertTrue((root / "app" / "projects" / cloned["project"]["id"]).is_dir())
            self.assertIn(cloned["project"]["id"], cloned["workspace"]["dirs"]["result"])
            self.assertNotEqual(cloned["workspace"]["dirs"]["result"], renamed_detail["workspace"]["dirs"]["result"])

            deleted = store.delete_project(renamed["id"])
            self.assertEqual(deleted["deleted"], renamed["id"])
            self.assertFalse((root / "app" / "projects" / renamed["id"]).exists())
            self.assertTrue(Path(deleted["trashed_to"]).is_dir())

    def test_save_project_uses_selected_control_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ProjectStore(root / "app" / "projects")
            workspace = self._make_workspace(root)

            saved = store.save_project(name="仅结果图", workspace=workspace, control_count=0)

            self.assertEqual(saved["project"]["control_count"], 0)
            self.assertEqual(saved["workspace"]["settings"]["control_count"], 0)
            self.assertNotIn("control1", saved["workspace"]["dirs"])
            self.assertIn("result", saved["workspace"]["dirs"])

    def test_update_ui_state_preserves_common_caption_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ProjectStore(root / "app" / "projects")
            workspace = self._make_workspace(root)
            saved = store.save_project(name="标注配置项目", workspace=workspace)
            project_id = saved["project"]["id"]

            ui_state = {
                "caption_settings": {
                    "local_overwrite_mode": "skip",
                    "local_caption_mode": "tag",
                    "local_max_tokens": "1024",
                    "local_prompt": "只输出短标签",
                },
                "template_selections": {
                    "customPrompt": "template-tag",
                },
            }
            updated = store.update_ui_state(project_id, ui_state)
            reopened = store.get_project(project_id)

            self.assertEqual(updated["workspace"]["ui_state"], ui_state)
            self.assertEqual(reopened["workspace"]["ui_state"], ui_state)
            self.assertEqual(
                (root / "app" / "projects" / project_id / "state" / "caption_config.json").read_text(encoding="utf-8"),
                '{\n  "local_overwrite_mode": "skip",\n  "local_caption_mode": "tag",\n  "local_max_tokens": "1024",\n  "local_prompt": "只输出短标签"\n}',
            )

    def test_legacy_project_store_directory_is_migrated_to_new_brand_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy_projects_dir = root / ".lora_dataset_edit" / "projects"
            new_projects_dir = root / ".vision_dataset_studio" / "projects"

            legacy_store = ProjectStore(legacy_projects_dir)
            workspace = self._make_workspace(root)
            saved = legacy_store.save_project(name="迁移项目", workspace=workspace)
            project_id = saved["project"]["id"]

            migrated_store = ProjectStore(new_projects_dir, legacy_projects_dir=legacy_projects_dir)
            projects = migrated_store.list_projects()

            self.assertEqual(len(projects), 1)
            self.assertEqual(projects[0]["id"], project_id)
            self.assertTrue((new_projects_dir / project_id).is_dir())
            self.assertFalse((legacy_projects_dir / project_id).exists())
            reopened = migrated_store.get_project(project_id)
            self.assertEqual(reopened["project"]["name"], "迁移项目")


if __name__ == "__main__":
    unittest.main()
