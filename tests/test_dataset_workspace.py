import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from PIL import Image

import dataset_workspace
from dataset_exporter import ExportCancelled, export_dataset
from dataset_image_processor import process_workspace_images
from dataset_workspace import (
    DatasetWorkspace,
    _delete_caption_segments,
    _parse_caption_segments,
    _replace_caption_segment,
)


class DatasetWorkspaceTextTests(unittest.TestCase):
    def setUp(self):
        self._state_tmp = tempfile.TemporaryDirectory()
        self._old_workspace_state_dir = dataset_workspace.WORKSPACE_STATE_DIR
        dataset_workspace.WORKSPACE_STATE_DIR = Path(self._state_tmp.name) / "workspaces"

    def tearDown(self):
        dataset_workspace.WORKSPACE_STATE_DIR = self._old_workspace_state_dir
        self._state_tmp.cleanup()

    def test_parse_caption_segments_multi_separators(self):
        value = "a, b，c; d；e\nf"
        self.assertEqual(_parse_caption_segments(value), ["a", "b", "c", "d", "e", "f"])

    def test_delete_caption_segments_keeps_layout(self):
        value = "A girl near window,\nsoft light; blue dress"
        updated = _delete_caption_segments(value, ["soft light"])
        self.assertEqual(updated, "A girl near window,\nblue dress")

    def test_replace_caption_segment_keeps_layout(self):
        value = "A girl near window,\nsoft light; blue dress"
        updated = _replace_caption_segment(value, "soft light", "warm light")
        self.assertEqual(updated, "A girl near window,\nwarm light; blue dress")

    def test_replace_caption_segment_delete(self):
        value = "A girl near window,\nsoft light; blue dress"
        updated = _replace_caption_segment(value, "soft light", "")
        self.assertEqual(updated, "A girl near window,\nblue dress")

    def test_workspace_save_and_search(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as result_dir:
            result_path = Path(result_dir)
            (result_path / "sample.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            workspace.open_dirs(result_dir=str(result_path), control_count=1)
            workspace.save_text("sample", "A girl near window,\nsoft light")
            item = workspace.get_item("sample")
            self.assertEqual(item["text"], "A girl near window,\nsoft light")
            data = workspace.list_items(tag_query="window")
            self.assertEqual(len(data["items"]), 1)
            self.assertNotIn("text", data["items"][0])
            detail = workspace.list_items(tag_query="window", detail=True)
            self.assertEqual(detail["items"][0]["text"], "A girl near window,\nsoft light")
            summary = workspace.list_items(tag_query="soft")
            self.assertEqual(summary["items"][0]["search_matches"]["segments"], ["soft light"])

    def test_workspace_search_matches_nested_item_name(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as result_dir:
            result_path = Path(result_dir)
            (result_path / "style").mkdir()
            (result_path / "style" / "sample_pose.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            workspace.open_dirs(result_dir=str(result_path), control_count=1)

            self.assertEqual(
                [item["name"] for item in workspace.list_items(tag_query="style/sample")["items"]],
                ["style/sample_pose"],
            )
            self.assertEqual(
                [item["name"] for item in workspace.list_items(tag_query="sample_pose")["items"]],
                ["style/sample_pose"],
            )
            data = workspace.list_items(tag_query="style/sample")
            self.assertTrue(data["items"][0]["search_matches"]["name"])

    def test_open_dirs_empty_string_clears_optional_role(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as control_dir, tempfile.TemporaryDirectory() as result_dir:
            control_path = Path(control_dir)
            result_path = Path(result_dir)
            Image.new("RGB", (32, 32), (10, 20, 30)).save(control_path / "sample.png")
            Image.new("RGB", (32, 32), (30, 20, 10)).save(result_path / "sample.png")
            workspace.open_dirs(control1_dir=str(control_path), result_dir=str(result_path), control_count=1)
            self.assertEqual(workspace.get_workspace_summary()["counts"]["control1"], 1)
            workspace.open_dirs(control1_dir="")
            summary = workspace.get_workspace_summary()
            self.assertEqual(summary["dirs"]["control1"], "")
            self.assertEqual(summary["counts"]["control1"], 0)

    def test_open_dirs_scans_nested_image_paths(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as control_dir, tempfile.TemporaryDirectory() as result_dir:
            control_path = Path(control_dir)
            result_path = Path(result_dir)
            (control_path / "style" / "day").mkdir(parents=True)
            (result_path / "style" / "day").mkdir(parents=True)
            Image.new("RGB", (32, 32), (10, 20, 30)).save(control_path / "style" / "day" / "sample.png")
            Image.new("RGB", (32, 32), (30, 20, 10)).save(result_path / "style" / "day" / "sample.png")
            (result_path / "style" / "day" / "sample.txt").write_text("nested caption", encoding="utf-8")

            workspace.open_dirs(control1_dir=str(control_path), result_dir=str(result_path), control_count=1)

            self.assertIn("style/day/sample", workspace.file_names)
            item = workspace.get_item("style/day/sample")
            self.assertEqual(item["text"], "nested caption")
            self.assertTrue(item["exists"]["control1"])
            self.assertTrue(item["exists"]["result"])

    def test_rename_item_changes_basename_only(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as control_dir, tempfile.TemporaryDirectory() as result_dir:
            control_path = Path(control_dir)
            result_path = Path(result_dir)
            (control_path / "style" / "day").mkdir(parents=True)
            (result_path / "style" / "day").mkdir(parents=True)
            Image.new("RGB", (32, 32), (10, 20, 30)).save(control_path / "style" / "day" / "sample.png")
            Image.new("RGB", (32, 32), (30, 20, 10)).save(result_path / "style" / "day" / "sample.webp")
            (result_path / "style" / "day" / "sample.txt").write_text("nested caption", encoding="utf-8")

            workspace.open_dirs(control1_dir=str(control_path), result_dir=str(result_path), control_count=1)
            result = workspace.rename_item("style/day/sample", "renamed")

            self.assertEqual(result["new_name"], "style/day/renamed")
            self.assertFalse((control_path / "style" / "day" / "sample.png").exists())
            self.assertFalse((result_path / "style" / "day" / "sample.webp").exists())
            self.assertTrue((control_path / "style" / "day" / "renamed.png").exists())
            self.assertTrue((result_path / "style" / "day" / "renamed.webp").exists())
            self.assertTrue((result_path / "style" / "day" / "renamed.txt").exists())
            self.assertIn("style/day/renamed", workspace.file_names)
            self.assertNotIn("style/day/sample", workspace.file_names)
            self.assertEqual(workspace.get_item("style/day/renamed")["text"], "nested caption")

    def test_rename_item_rejects_folder_paths(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as result_dir:
            result_path = Path(result_dir)
            Image.new("RGB", (32, 32), (30, 20, 10)).save(result_path / "sample.png")
            workspace.open_dirs(result_dir=str(result_path), control_count=1)

            with self.assertRaises(ValueError):
                workspace.rename_item("sample", "other/name")

    def test_move_item_to_folder_changes_parent_only(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as control_dir, tempfile.TemporaryDirectory() as result_dir:
            control_path = Path(control_dir)
            result_path = Path(result_dir)
            (control_path / "style" / "day").mkdir(parents=True)
            (result_path / "style" / "day").mkdir(parents=True)
            Image.new("RGB", (32, 32), (10, 20, 30)).save(control_path / "style" / "day" / "sample.png")
            Image.new("RGB", (32, 32), (30, 20, 10)).save(result_path / "style" / "day" / "sample.webp")
            (result_path / "style" / "day" / "sample.txt").write_text("nested caption", encoding="utf-8")

            workspace.open_dirs(control1_dir=str(control_path), result_dir=str(result_path), control_count=1)
            result = workspace.move_item_to_folder("style/day/sample", "icons")

            self.assertEqual(result["new_name"], "icons/sample")
            self.assertFalse((control_path / "style" / "day" / "sample.png").exists())
            self.assertFalse((result_path / "style" / "day" / "sample.webp").exists())
            self.assertTrue((control_path / "icons" / "sample.png").exists())
            self.assertTrue((result_path / "icons" / "sample.webp").exists())
            self.assertTrue((result_path / "icons" / "sample.txt").exists())
            self.assertIn("icons/sample", workspace.file_names)
            self.assertEqual(workspace.get_item("icons/sample")["text"], "nested caption")

    def test_trash_item_files_removes_source_files_and_workspace_item(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as control_dir, tempfile.TemporaryDirectory() as result_dir:
            control_path = Path(control_dir)
            result_path = Path(result_dir)
            control_file = control_path / "sample.png"
            result_file = result_path / "sample.webp"
            txt_file = result_path / "sample.txt"
            Image.new("RGB", (32, 32), (10, 20, 30)).save(control_file)
            Image.new("RGB", (32, 32), (30, 20, 10)).save(result_file)
            txt_file.write_text("caption", encoding="utf-8")

            workspace.open_dirs(control1_dir=str(control_path), result_dir=str(result_path), control_count=1)

            def fake_trash(path):
                Path(path).unlink()

            with mock.patch("dataset_workspace._send_to_trash", side_effect=fake_trash) as send_to_trash:
                result = workspace.trash_item_files("sample")

            self.assertEqual(send_to_trash.call_count, 3)
            self.assertFalse(control_file.exists())
            self.assertFalse(result_file.exists())
            self.assertFalse(txt_file.exists())
            self.assertEqual(result["removed_name"], "sample")
            self.assertNotIn("sample", workspace.file_names)
            self.assertEqual(workspace.get_workspace_summary()["counts"]["all"], 0)

    def test_apply_name_aliases_restores_relative_item_name(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as result_dir:
            result_path = Path(result_dir)
            Image.new("RGB", (32, 32), (30, 20, 10)).save(result_path / "display_off.png")
            workspace.open_dirs(result_dir=str(result_path), control_count=1)

            summary = workspace.apply_name_aliases({"display_off": "system/display_off"})
            items = workspace.list_items()["items"]

            self.assertEqual(summary["counts"]["all"], 1)
            self.assertEqual(items[0]["name"], "system/display_off")
            self.assertIsNotNone(workspace.resolve_image_path("result", "system/display_off"))

    def test_merge_dirs_appends_additional_dataset(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as base_control, \
                tempfile.TemporaryDirectory() as base_result, \
                tempfile.TemporaryDirectory() as extra_control, \
                tempfile.TemporaryDirectory() as extra_result:
            Image.new("RGB", (32, 32), (10, 20, 30)).save(Path(base_control) / "sample.png")
            Image.new("RGB", (32, 32), (30, 20, 10)).save(Path(base_result) / "sample.png")
            (Path(base_result) / "sample.txt").write_text("base caption", encoding="utf-8")
            Image.new("RGB", (32, 32), (40, 50, 60)).save(Path(extra_control) / "sample.png")
            Image.new("RGB", (32, 32), (60, 50, 40)).save(Path(extra_result) / "sample.png")
            (Path(extra_result) / "sample.txt").write_text("extra caption", encoding="utf-8")

            workspace.open_dirs(control1_dir=base_control, result_dir=base_result, control_count=1)
            result = workspace.merge_dirs(control1_dir=extra_control, result_dir=extra_result, control_count=1)

            self.assertEqual(result["merged"], 1)
            self.assertEqual(result["workspace"]["counts"]["all"], 2)
            self.assertIn("sample", workspace.file_names)
            self.assertIn("sample [2]", workspace.file_names)
            self.assertEqual(workspace.get_item("sample [2]")["text"], "extra caption")

    def test_swap_control_result_pairs_copies_inverse_pair(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as control_dir, tempfile.TemporaryDirectory() as result_dir:
            control_path = Path(control_dir)
            result_path = Path(result_dir)
            (control_path / "style" / "day").mkdir(parents=True)
            (result_path / "style" / "day").mkdir(parents=True)
            control_image = control_path / "style" / "day" / "sample.png"
            result_image = result_path / "style" / "day" / "sample.png"
            Image.new("RGB", (16, 16), (10, 20, 30)).save(control_image)
            Image.new("RGB", (16, 16), (90, 80, 70)).save(result_image)
            (result_path / "style" / "day" / "sample.txt").write_text("source caption", encoding="utf-8")

            workspace.open_dirs(control1_dir=str(control_path), result_dir=str(result_path), control_count=1)
            result = workspace.swap_control_result_pairs(
                control_dir=str(control_path),
                result_dir=str(result_path),
                suffix="_flip",
            )

            self.assertEqual(result["swapped"], 1)
            self.assertTrue(control_image.exists())
            self.assertTrue(result_image.exists())
            control_copy = control_path / "style" / "day" / "sample_flip.png"
            result_copy = result_path / "style" / "day" / "sample_flip.png"
            self.assertTrue(control_copy.exists())
            self.assertTrue(result_copy.exists())
            with Image.open(control_copy) as image:
                self.assertEqual(image.getpixel((0, 0)), (90, 80, 70))
            with Image.open(result_copy) as image:
                self.assertEqual(image.getpixel((0, 0)), (10, 20, 30))
            self.assertIn("style/day/sample", workspace.file_names)
            self.assertIn("style/day/sample_flip", workspace.file_names)
            self.assertEqual(workspace.get_workspace_summary()["counts"]["all"], 2)
            self.assertEqual(workspace.get_workspace_summary()["counts"]["txt"], 1)

    def test_batch_add_delete_replace(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as result_dir:
            result_path = Path(result_dir)
            (result_path / "sample.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            workspace.open_dirs(result_dir=str(result_path), control_count=1)
            workspace.save_text("sample", "A girl near window")
            workspace.batch_add_segments(["sample"], ["soft light"])
            self.assertEqual(workspace.get_item("sample")["text"], "A girl near window; soft light")
            workspace.batch_add_segments(["sample"], ["masterpiece"], position="before")
            self.assertEqual(workspace.get_item("sample")["text"], "masterpiece; A girl near window; soft light")
            workspace.batch_replace_segment(["sample"], "soft light", "warm light")
            self.assertIn("warm light", workspace.get_item("sample")["text"])
            workspace.batch_delete_segments(["sample"], ["warm light"])
            self.assertNotIn("warm light", workspace.get_item("sample")["text"])

    def test_batch_rename_items_updates_images_and_txt(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as control_dir, tempfile.TemporaryDirectory() as result_dir:
            control_path = Path(control_dir)
            result_path = Path(result_dir)
            Image.new("RGB", (32, 32), (10, 20, 30)).save(control_path / "sample.png")
            Image.new("RGB", (32, 32), (30, 20, 10)).save(result_path / "sample.webp")
            (result_path / "sample.txt").write_text("caption", encoding="utf-8")
            workspace.open_dirs(control1_dir=str(control_path), result_dir=str(result_path), control_count=1)

            result = workspace.batch_rename_items(["sample"], operation="add_prefix", value="pre_")
            self.assertEqual(result["changed"], 1)
            self.assertTrue((control_path / "pre_sample.png").exists())
            self.assertTrue((result_path / "pre_sample.webp").exists())
            self.assertTrue((result_path / "pre_sample.txt").exists())

            result = workspace.batch_rename_items(["pre_sample"], operation="add_suffix", value="_tail")
            self.assertEqual(result["changed"], 1)
            self.assertIn("pre_sample_tail", workspace.file_names)

            result = workspace.batch_rename_items(["pre_sample_tail"], operation="delete", value="pre_,_tail")
            self.assertEqual(result["changed"], 1)
            self.assertIn("sample", workspace.file_names)

            result = workspace.batch_rename_items(["sample"], operation="replace", old_value="sample", new_value="renamed")
            self.assertEqual(result["changed"], 1)
            item = workspace.get_item("renamed")
            self.assertEqual(item["text"], "caption")
            self.assertTrue(item["exists"]["control1"])
            self.assertTrue(item["exists"]["result"])
            self.assertTrue((result_path / "renamed.txt").exists())

    def test_global_segments_keeps_legacy_global_tags(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as result_dir:
            result_path = Path(result_dir)
            (result_path / "sample.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            workspace.open_dirs(result_dir=str(result_path), control_count=1)
            workspace.save_text("sample", "soft light, blue dress")
            data = workspace.list_items()
            self.assertEqual(data["global_segments"], data["global_tags"])
            self.assertEqual(data["global_segments"][0]["segment"], "blue dress")

    def test_global_segments_cache_invalidates_on_save_and_delete(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as result_dir:
            result_path = Path(result_dir)
            (result_path / "sample.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            workspace.open_dirs(result_dir=str(result_path), control_count=1)
            workspace.save_text("sample", "soft light")
            self.assertEqual(workspace.get_global_segments()[0]["segment"], "soft light")
            workspace.save_text("sample", "warm light")
            self.assertEqual(workspace.get_global_segments()[0]["segment"], "warm light")
            workspace.delete_item("sample")
            self.assertEqual(workspace.get_global_segments(), [])

    def test_save_text_does_not_modify_source_txt(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as result_dir:
            result_path = Path(result_dir)
            (result_path / "sample.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            source_txt = result_path / "sample.txt"
            source_txt.write_text("source caption", encoding="utf-8")
            workspace.open_dirs(result_dir=str(result_path), control_count=1)
            workspace.save_text("sample", "edited caption")
            self.assertEqual(source_txt.read_text(encoding="utf-8"), "source caption")
            self.assertEqual(workspace.get_item("sample")["text"], "edited caption")
            self.assertEqual(workspace.get_item("sample")["caption_source"], "edited")

    def test_clearing_saved_caption_marks_item_missing_txt(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as result_dir:
            result_path = Path(result_dir)
            (result_path / "sample.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            source_txt = result_path / "sample.txt"
            source_txt.write_text("source caption", encoding="utf-8")
            workspace.open_dirs(result_dir=str(result_path), control_count=1)

            workspace.save_text("sample", "")
            item = workspace.get_item("sample")
            self.assertFalse(item["exists"]["txt"])
            self.assertEqual(item["text"], "")
            self.assertEqual(item["caption_source"], "")
            self.assertEqual(source_txt.read_text(encoding="utf-8"), "source caption")
            self.assertEqual(workspace.get_workspace_summary()["counts"]["txt"], 0)
            self.assertEqual(workspace.list_items(filter_mode="no_txt")["items"][0]["name"], "sample")

            reopened = DatasetWorkspace()
            reopened.open_dirs(result_dir=str(result_path), control_count=1)
            self.assertFalse(reopened.get_item("sample")["exists"]["txt"])

    def test_export_dataset_zip_resizes_to_multiple(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as result_dir, tempfile.TemporaryDirectory() as export_dir:
            result_path = Path(result_dir)
            Image.new("RGB", (1200, 800), (120, 80, 40)).save(result_path / "sample.png")
            workspace.open_dirs(result_dir=str(result_path), control_count=1)
            workspace.save_text("sample", "edited caption")
            result = export_dataset(
                items=workspace.get_export_items(),
                output_format="zip",
                output_dir=export_dir,
                target_megapixels=1,
                multiple=32,
                process_images=True,
                include_controls=False,
            )
            self.assertEqual(result["format"], "zip")
            self.assertEqual(result["exported"], 1)
            self.assertGreater(len(result["bytes"]), 0)
            zip_path = Path(result["path"])
            self.assertTrue(zip_path.exists())

    def test_export_dataset_zip_progress_tracks_archive_writes(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as result_dir, tempfile.TemporaryDirectory() as export_dir:
            result_path = Path(result_dir)
            Image.new("RGB", (512, 512), (120, 80, 40)).save(result_path / "sample.png")
            workspace.open_dirs(result_dir=str(result_path), control_count=1)
            workspace.save_text("sample", "edited caption")
            events = []

            result = export_dataset(
                items=workspace.get_export_items(),
                output_format="zip",
                output_dir=export_dir,
                target_megapixels=1,
                multiple=16,
                process_images=False,
                include_controls=False,
                include_bytes=False,
                progress_callback=lambda row: events.append(dict(row)),
            )

            self.assertEqual(result["format"], "zip")
            self.assertNotIn("bytes", result)
            self.assertTrue(events)
            self.assertEqual(events[0]["total"], 6)
            self.assertEqual(events[-1]["done"], events[-1]["total"])

    def test_export_dataset_cancel_cleans_partial_output(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as result_dir, tempfile.TemporaryDirectory() as export_dir:
            result_path = Path(result_dir)
            Image.new("RGB", (512, 512), (120, 80, 40)).save(result_path / "sample.png")
            workspace.open_dirs(result_dir=str(result_path), control_count=1)
            stop = {"value": False}

            def progress(row):
                if row.get("done", 0) >= 1:
                    stop["value"] = True

            with self.assertRaises(ExportCancelled):
                export_dataset(
                    items=workspace.get_export_items(),
                    output_format="folder",
                    output_dir=export_dir,
                    target_megapixels=1,
                    multiple=16,
                    process_images=False,
                    include_controls=False,
                    progress_callback=progress,
                    should_stop=lambda: stop["value"],
                )

            self.assertEqual(list(Path(export_dir).iterdir()), [])

    def test_export_dataset_folder_writes_caption(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as result_dir, tempfile.TemporaryDirectory() as export_dir:
            result_path = Path(result_dir)
            Image.new("RGB", (512, 512), (120, 80, 40)).save(result_path / "sample.png")
            workspace.open_dirs(result_dir=str(result_path), control_count=1)
            workspace.save_text("sample", "edited caption")
            result = export_dataset(
                items=workspace.get_export_items(),
                output_format="folder",
                output_dir=export_dir,
                target_megapixels=1,
                multiple=16,
                process_images=False,
                include_controls=False,
            )
            export_path = Path(result["path"])
            result_dir = export_path / f"{export_path.name}_result"
            self.assertTrue((result_dir / "sample.txt").exists())
            self.assertEqual((result_dir / "sample.txt").read_text(encoding="utf-8"), "edited caption")

    def test_export_dataset_zip_uses_project_role_folders_and_shared_names(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as control_dir, \
                tempfile.TemporaryDirectory() as result_dir, \
                tempfile.TemporaryDirectory() as export_dir:
            control_path = Path(control_dir)
            result_path = Path(result_dir)
            Image.new("RGB", (512, 512), (20, 80, 140)).save(control_path / "sample.png")
            Image.new("RGB", (512, 512), (120, 80, 40)).save(result_path / "sample.png")
            workspace.open_dirs(control1_dir=str(control_path), result_dir=str(result_path), control_count=1)
            workspace.save_text("sample", "edited caption")
            result = export_dataset(
                items=workspace.get_export_items(),
                output_format="zip",
                output_dir=export_dir,
                project_name="越野风格",
                target_megapixels=4,
                multiple=16,
                process_images=False,
                include_controls=True,
                control_count=1,
            )

            export_prefix = Path(result["path"]).stem
            control_folder = f"{export_prefix}_control1"
            result_folder = f"{export_prefix}_result"
            with zipfile.ZipFile(result["path"]) as archive:
                names = set(archive.namelist())

            self.assertIn(f"{control_folder}/sample.png", names)
            self.assertIn(f"{result_folder}/sample.png", names)
            self.assertIn(f"{result_folder}/sample.txt", names)
            self.assertIn("manifest.json", names)
            self.assertFalse(any(name.startswith(f"{export_prefix}/") for name in names))

    def test_export_dataset_zip_can_preserve_subfolders(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as control_dir, \
                tempfile.TemporaryDirectory() as result_dir, \
                tempfile.TemporaryDirectory() as export_dir:
            control_path = Path(control_dir)
            result_path = Path(result_dir)
            (control_path / "style" / "day").mkdir(parents=True)
            (result_path / "style" / "day").mkdir(parents=True)
            Image.new("RGB", (512, 512), (20, 80, 140)).save(control_path / "style" / "day" / "sample.png")
            Image.new("RGB", (512, 512), (120, 80, 40)).save(result_path / "style" / "day" / "sample.png")
            workspace.open_dirs(control1_dir=str(control_path), result_dir=str(result_path), control_count=1)
            workspace.save_text("style/day/sample", "edited caption")

            result = export_dataset(
                items=workspace.get_export_items(),
                output_format="zip",
                output_dir=export_dir,
                project_name="nested",
                target_megapixels=4,
                multiple=16,
                process_images=False,
                include_controls=True,
                control_count=1,
                preserve_subfolders=True,
            )

            export_prefix = Path(result["path"]).stem
            control_folder = f"{export_prefix}_control1"
            result_folder = f"{export_prefix}_result"
            with zipfile.ZipFile(result["path"]) as archive:
                names = set(archive.namelist())

            self.assertIn(f"{control_folder}/style/day/sample.png", names)
            self.assertIn(f"{result_folder}/style/day/sample.png", names)
            self.assertIn(f"{result_folder}/style/day/sample.txt", names)
            self.assertNotIn(f"{result_folder}/sample.png", names)

    def test_process_workspace_images_creates_loadable_role_dirs(self):
        workspace = DatasetWorkspace()
        with tempfile.TemporaryDirectory() as control_dir, \
                tempfile.TemporaryDirectory() as result_dir, \
                tempfile.TemporaryDirectory() as process_dir:
            control_path = Path(control_dir)
            result_path = Path(result_dir)
            Image.new("RGB", (1200, 800), (20, 80, 140)).save(control_path / "sample.png")
            Image.new("RGB", (1200, 800), (120, 80, 40)).save(result_path / "sample.png")
            workspace.open_dirs(control1_dir=str(control_path), result_dir=str(result_path), control_count=1)
            workspace.save_text("sample", "edited caption")

            result = process_workspace_images(
                items=workspace.get_export_items(),
                output_dir=process_dir,
                project_name="标注前处理",
                target_megapixels=1,
                multiple=16,
                include_controls=True,
                control_count=1,
            )

            self.assertEqual(result["processed"], 1)
            processed_workspace = DatasetWorkspace()
            processed_workspace.open_dirs(
                control1_dir=result["dirs"]["control1"],
                result_dir=result["dirs"]["result"],
                control_count=1,
            )
            item = processed_workspace.get_item("sample")
            self.assertEqual(item["text"], "edited caption")
            self.assertTrue(item["exists"]["control1"])
            self.assertTrue(item["exists"]["result"])
            with Image.open(Path(result["dirs"]["result"]) / "sample.png") as processed_image:
                width, height = processed_image.size
            self.assertLessEqual(width * height, 1_000_000)
            self.assertEqual(width % 16, 0)
            self.assertEqual(height % 16, 0)

    def test_process_workspace_images_reports_progress(self):
        workspace = DatasetWorkspace()
        progress_rows = []
        with tempfile.TemporaryDirectory() as result_dir, tempfile.TemporaryDirectory() as process_dir:
            result_path = Path(result_dir)
            Image.new("RGB", (512, 512), (120, 80, 40)).save(result_path / "sample.png")
            workspace.open_dirs(result_dir=str(result_path), control_count=1)
            process_workspace_images(
                items=workspace.get_export_items(),
                output_dir=process_dir,
                project_name="progress",
                target_megapixels=1,
                multiple=16,
                include_controls=False,
                control_count=1,
                progress_callback=progress_rows.append,
            )

            self.assertGreaterEqual(len(progress_rows), 2)
            self.assertEqual(progress_rows[-1]["done"], 1)
            self.assertEqual(progress_rows[-1]["total"], 1)


if __name__ == "__main__":
    unittest.main()
