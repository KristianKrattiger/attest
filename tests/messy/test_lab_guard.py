"""Nothing committed under firm/lab names the lab tenant or its owner (spec 2026-10-14, Scrubbing and storage)."""
from messy.firm import LAB
from scripts.scrub_lab_capture import committed_leaks, read_deny

PLANTED = '{"lastExternalIpAddress": "203.45.67.89", "upn": "a@contosolab.onmicrosoft.com"}'


def test_nothing_committed_under_firm_lab_names_the_tenant_or_its_owner():
    # firm/lab/raw/deny.txt is on the machine that took the captures; elsewhere it is absent and the list is empty.
    assert committed_leaks(LAB, read_deny()) == []


def test_a_planted_leak_is_reported_and_the_same_content_under_raw_is_not(tmp_path):
    for folder in ("seed-clean/exports", "raw/seed-clean/exports"):
        (tmp_path / folder).mkdir(parents=True)
        (tmp_path / folder / "users.json").write_text(PLANTED, encoding="utf-8")
    assert committed_leaks(tmp_path, []) == [
        "seed-clean/exports/users.json: an onmicrosoft.com domain",
        "seed-clean/exports/users.json: public IP address 203.45.67.89"]
    (tmp_path / "seed-clean" / "exports" / "users.json").unlink()
    assert committed_leaks(tmp_path, []) == []


def test_a_denied_value_is_reported_as_a_whole_word_and_a_longer_word_is_not(tmp_path):
    (tmp_path / "notes.md").write_text("The owner is Pat. A patch is not a Pat.", encoding="utf-8")
    (tmp_path / "other.md").write_text("A patch and a pattern.", encoding="utf-8")
    assert committed_leaks(tmp_path, ["Pat"]) == ["notes.md: denied value 'Pat'"]


def test_a_file_that_is_not_text_is_reported_instead_of_crashing(tmp_path):
    (tmp_path / "seed-clean").mkdir()
    (tmp_path / "seed-clean" / "photo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    (tmp_path / "seed-clean" / "users.json").write_text(PLANTED, encoding="utf-8")
    assert committed_leaks(tmp_path, []) == [
        "seed-clean/photo.png: not UTF-8 or UTF-16 text",
        "seed-clean/users.json: an onmicrosoft.com domain",
        "seed-clean/users.json: public IP address 203.45.67.89"]


def test_a_utf16_file_is_read_and_a_missing_folder_has_nothing_to_report(tmp_path):
    (tmp_path / "users.json").write_bytes(b"\xff\xfe" + PLANTED.encode("utf-16-le"))
    assert committed_leaks(tmp_path, []) == [
        "users.json: an onmicrosoft.com domain", "users.json: public IP address 203.45.67.89"]
    assert committed_leaks(tmp_path / "absent", ["Pat"]) == []


def test_a_file_name_that_names_the_tenant_is_reported(tmp_path):
    (tmp_path / "contosolab.onmicrosoft.com.json").write_text("{}", encoding="utf-8")
    assert committed_leaks(tmp_path, []) == ["contosolab.onmicrosoft.com.json: in its name, an onmicrosoft.com domain"]
