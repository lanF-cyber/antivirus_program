from pathlib import Path

from scanbox.core.hashing import HashingService


def test_hashing_service_computes_sha256_md5_sha1() -> None:
    fixture = Path("tests/fixtures/benign/hello.txt")
    hashes = HashingService().compute(fixture)

    assert hashes.sha256 == "7695f47134674874eb282c60b628a0cbf08e735fb3d9ba1a908c0e0be72ba6d5"
    assert hashes.md5 == "9c915fde622438f2605b3474f034135a"
    assert hashes.sha1 == "7a1095da9ac659bbb0c4bda0f24be63020459827"
