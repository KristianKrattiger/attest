from attest.compare import check
from messy.firm import DEV, Firm, decode, healed_dev, records, seed, utf8_json

PROVABLE = {"mfa.email", "mfa.all_users", "mfa.admins", "edr.all_endpoints", "backup.m365_mailboxes"}


def test_decode_reads_utf16_utf8_with_a_bom_and_plain_utf8():
    text = '{"a": "é"}'
    assert decode(b"\xff\xfe" + text.encode("utf-16-le")) == text
    assert decode(b"\xef\xbb\xbf" + text.encode("utf-8")) == text
    assert decode(text.encode("utf-8")) == text


def test_records_are_a_page_s_value_a_list_or_one_object():
    assert records({"@odata.context": "x", "value": [{"id": 1}]}) == [{"id": 1}]
    assert records([{"id": 1}, {"id": 2}]) == [{"id": 1}, {"id": 2}]
    assert records({"id": 1}) == [{"id": 1}]


def test_a_firm_written_out_loads_back_the_same(tmp_path):
    firm = Firm.load(DEV / "exports")
    again = Firm.load(firm.write(tmp_path / "firm") / "exports")
    assert again.data == firm.data
    assert [e["file"] for e in again.manifest] == [e["file"] for e in firm.manifest]
    assert again.exported_at("entra_users") == firm.exported_at("entra_users")


def test_a_copy_is_independent_of_its_original():
    firm = Firm.load(DEV / "exports")
    copied = firm.copy()
    copied.rows("entra_users")[0]["displayName"] = "Changed"
    copied.touched.add("user:x")
    assert firm.rows("entra_users")[0]["displayName"] != "Changed" and not firm.touched


def test_a_writer_decides_how_a_file_is_written(tmp_path):
    firm = Firm.load(DEV / "exports")
    firm.writers["users.json"] = lambda data: b"\xef\xbb\xbf" + utf8_json(data)
    folder = firm.write(tmp_path / "firm")
    assert (folder / "exports" / "users.json").read_bytes().startswith(b"\xef\xbb\xbf{")
    assert not (folder / "exports" / "registration.json").read_bytes().startswith(b"\xef\xbb\xbf")


def test_the_healed_dev_firm_is_backed_wherever_a_scope_can_be_proven(tmp_path):
    for tag, verdict in check(healed_dev().write(tmp_path / "firm")):
        assert verdict.status == ("backed" if f"{tag.control}.{tag.scope}" in PROVABLE else "unchecked"), tag.id


def test_the_seed_is_the_healed_dev_firm_until_seed_clean_is_committed():
    name, firm = seed()
    assert name in ("dev", "seed-clean")
    if name == "dev":
        assert firm.data == healed_dev().data
