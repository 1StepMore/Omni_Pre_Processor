import sys
from pathlib import Path
import uuid
import pytest
import importlib.util

@pytest.fixture
def createMinimalPNG():
    def _createMinimalPNG(width=10, height=10):
        import zlib, struct
        def png_chunk(chunk_type, data):
            chunk = chunk_type + data
            crc = zlib.crc32(chunk) & 0xffffffff
            return struct.pack('>I', len(data)) + chunk + struct.pack('>I', crc)
        header = b'\x89PNG\r\n\x1a\n'
        ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
        raw = b'RGB' * width * height
        idat = zlib.compress(raw)
        return header + png_chunk(b'IHDR', ihdr) + png_chunk(b'IDAT', idat) + png_chunk(b'IEND', b'')
    return _createMinimalPNG

class OPPError(Exception):
    pass


spec = importlib.util.spec_from_file_location("resource_manager", Path(__file__).parent.parent / "src" / "opp" / "resource_manager.py")
resource_manager_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resource_manager_module)
ResourceManager = resource_manager_module.ResourceManager


class TestResourceManager:

    def test_add_image_stores_file(self, tmp_path: Path, createMinimalPNG):
        manager = ResourceManager(tmp_path)
        source = tmp_path / "source.png"
        source.write_bytes(createMinimalPNG())

        stored_path = manager.add_image(source)

        assert stored_path.exists()
        assert stored_path.parent == tmp_path

    def test_md5_deduplication_same_file(self, tmp_path: Path, createMinimalPNG):
        storage_dir = tmp_path / "storage"
        manager = ResourceManager(storage_dir)
        source = tmp_path / "source.png"
        source.write_bytes(createMinimalPNG())

        path1 = manager.add_image(source)
        path2 = manager.add_image(source)

        assert path1 == path2
        assert len(list(storage_dir.iterdir())) == 1

    def test_md5_deduplication_different_content_same_bytes(self, tmp_path: Path, createMinimalPNG):
        storage_dir = tmp_path / "storage"
        manager = ResourceManager(storage_dir)
        source1 = tmp_path / "source1.png"
        source2 = tmp_path / "source2.png"
        png_data = createMinimalPNG()
        source1.write_bytes(png_data)
        source2.write_bytes(png_data)

        path1 = manager.add_image(source1)
        path2 = manager.add_image(source2)

        assert path1 == path2
        assert len(list(storage_dir.iterdir())) == 1

    def test_uuid_naming_different_files(self, tmp_path: Path, createMinimalPNG):
        storage_dir = tmp_path / "storage"
        manager = ResourceManager(storage_dir)
        source1 = tmp_path / "source1.png"
        source2 = tmp_path / "source2.png"
        source1.write_bytes(createMinimalPNG(10, 10))
        source2.write_bytes(createMinimalPNG(20, 20))

        path1 = manager.add_image(source1)
        path2 = manager.add_image(source2)

        name1 = path1.name
        name2 = path2.name
        assert name1 != name2
        uuid1 = name1.rsplit('.', 1)[0]
        uuid2 = name2.rsplit('.', 1)[0]
        uuid.UUID(uuid1)
        uuid.UUID(uuid2)

    def test_get_mapping_returns_correct_dict(self, tmp_path: Path, createMinimalPNG):
        manager = ResourceManager(tmp_path)
        source1 = tmp_path / "first.png"
        source2 = tmp_path / "second.png"
        source1.write_bytes(createMinimalPNG(10, 10))
        source2.write_bytes(createMinimalPNG(20, 20))

        path1 = manager.add_image(source1)
        path2 = manager.add_image(source2)

        mapping = manager.get_mapping()
        assert mapping == {"first.png": path1, "second.png": path2}

    def test_get_mapping_after_deduplication(self, tmp_path: Path, createMinimalPNG):
        manager = ResourceManager(tmp_path)
        source1 = tmp_path / "original.png"
        source2 = tmp_path / "copy.png"
        png_data = createMinimalPNG()
        source1.write_bytes(png_data)
        source2.write_bytes(png_data)

        manager.add_image(source1)
        manager.add_image(source2)

        mapping = manager.get_mapping()
        assert len(mapping) == 1
        assert "original.png" in mapping or "copy.png" in mapping

    def test_empty_manager_get_mapping(self, tmp_path: Path):
        manager = ResourceManager(tmp_path)
        mapping = manager.get_mapping()
        assert mapping == {}

    def test_add_image_creates_storage_dir(self, tmp_path: Path, createMinimalPNG):
        storage_dir = tmp_path / "nested" / "storage"
        manager = ResourceManager(storage_dir)
        source = tmp_path / "source.png"
        source.write_bytes(createMinimalPNG())

        manager.add_image(source)

        assert storage_dir.exists()

    def test_add_image_file_not_found(self, tmp_path: Path):
        manager = ResourceManager(tmp_path)
        with pytest.raises(FileNotFoundError):
            manager.add_image(tmp_path / "nonexistent.png")

    def test_many_images_many_unique(self, tmp_path: Path, createMinimalPNG):
        storage_dir = tmp_path / "storage"
        manager = ResourceManager(storage_dir)
        count = 100

        paths = []
        for i in range(count):
            source = tmp_path / f"source_{i}.png"
            source.write_bytes(createMinimalPNG(i + 1, i + 1))
            paths.append(manager.add_image(source))

        assert len(set(paths)) == count
        assert len(list(storage_dir.iterdir())) == count

    def test_extension_preserved(self, tmp_path: Path, createMinimalPNG):
        storage_dir = tmp_path / "storage"
        manager = ResourceManager(storage_dir)

        extensions = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
        for idx, ext in enumerate(extensions):
            source = tmp_path / f"source{ext}"
            source.write_bytes(createMinimalPNG(width=10 + idx, height=10 + idx))
            stored = manager.add_image(source)
            assert stored.suffix == ext

    def test_no_extension_gets_bin(self, tmp_path: Path, createMinimalPNG):
        manager = ResourceManager(tmp_path)
        source = tmp_path / "noextension"
        source.write_bytes(createMinimalPNG())

        stored = manager.add_image(source)

        assert stored.suffix == ".bin"

    def test_md5_computed_correctly(self, tmp_path: Path, createMinimalPNG):
        manager = ResourceManager(tmp_path)
        source = tmp_path / "source.png"
        png_data = createMinimalPNG()
        source.write_bytes(png_data)

        md5_1 = manager._compute_file_md5(source)
        md5_2 = manager._compute_file_md5(source)

        assert md5_1 == md5_2
        assert len(md5_1) == 32
        assert all(c in '0123456789abcdef' for c in md5_1)

    def test_different_content_different_md5(self, tmp_path: Path, createMinimalPNG):
        manager = ResourceManager(tmp_path)
        source1 = tmp_path / "source1.png"
        source2 = tmp_path / "source2.png"
        source1.write_bytes(createMinimalPNG(10, 10))
        source2.write_bytes(createMinimalPNG(20, 20))

        md5_1 = manager._compute_file_md5(source1)
        md5_2 = manager._compute_file_md5(source2)

        assert md5_1 != md5_2
