import logging

from bejitech.config.logging_setup import setup_logging
from bejitech.security.keystore import FileKeyStore
from bejitech.selftest import run_self_test


def test_file_keystore_roundtrip(tmp_path):
    ks = FileKeyStore(tmp_path / "k")
    assert ks.load() is None
    ks.save(b"x" * 32)
    assert ks.load() == b"x" * 32
    assert oct((tmp_path / "k").stat().st_mode)[-3:] == "600"


def test_log_redacts_keys(tmp_path):
    setup_logging(tmp_path)
    logging.getLogger("t").warning("sold ABCDE-FGHIJ-KLMNO-PQRST-7HQ2D today")
    for h in logging.getLogger().handlers:
        h.flush()
    text = (tmp_path / "app.log").read_text()
    assert "[REDACTED-KEY]" in text and "ABCDE-FGHIJ" not in text


def test_self_test_passes(capsys):
    assert run_self_test() == 0
    assert "ALL PASSED" in capsys.readouterr().out
