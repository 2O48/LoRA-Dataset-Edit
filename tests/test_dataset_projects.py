import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
