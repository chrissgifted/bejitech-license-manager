import pytest

from bejitech.core.errors import KeyStoreError
from bejitech.security import crypto, passwords
from bejitech.security.crypto import CipherBox
from bejitech.security.masking import last_chars, mask_key, normalize_key, redact


def test_encrypt_roundtrip_and_aad_binding():
    box = CipherBox(crypto.generate_key())
    ct, nonce = box.encrypt_license_key("ABCDE-12345-FGHIJ-67890-KLMNO", "uuid-1")
    assert b"ABCDE" not in ct
    assert box.decrypt_license_key(ct, nonce, "uuid-1") == "ABCDE-12345-FGHIJ-67890-KLMNO"
    with pytest.raises(KeyStoreError):
        box.decrypt_license_key(ct, nonce, "uuid-2")  # ciphertext moved to another record


def test_wrong_key_fails():
    ct, nonce = CipherBox(crypto.generate_key()).encrypt_license_key("SECRET", "u")
    with pytest.raises(KeyStoreError):
        CipherBox(crypto.generate_key()).decrypt_license_key(ct, nonce, "u")


def test_fingerprint_normalises():
    box = CipherBox(crypto.generate_key())
    assert box.fingerprint("abcde-fghij") == box.fingerprint(" ABCDE-FGHIJ ")


def test_dek_check():
    box = CipherBox(crypto.generate_key())
    blob = box.make_check()
    assert box.verify_check(blob)
    assert not CipherBox(crypto.generate_key()).verify_check(blob)


def test_password_hash():
    h = passwords.hash_password("s3cret-pass")
    assert h.startswith("$argon2id$")
    assert passwords.verify_password(h, "s3cret-pass")
    assert not passwords.verify_password(h, "wrong")


def test_kdf_deterministic_with_same_salt():
    params = passwords.new_kdf_params()
    assert passwords.derive_key("x", params) == passwords.derive_key("x", params)
    assert passwords.derive_key("x", params) != passwords.derive_key("y", params)


def test_masking_and_redaction():
    assert normalize_key("ab cd-ef") == "ABCD-EF"
    assert last_chars("ABCDE-FGHIJ-KLMNO-PQRST-7HQ2D") == "7HQ2D"
    assert mask_key("7HQ2D") == "XXXXX-XXXXX-XXXXX-XXXXX-7HQ2D"
    assert "ABCDE" not in redact("key ABCDE-FGHIJ-KLMNO-PQRST-7HQ2D sold")


def test_env_keystore(monkeypatch):
    import base64

    import pytest

    from bejitech.core.errors import KeyStoreError
    from bejitech.security.keystore import EnvKeyStore

    ks = EnvKeyStore()
    monkeypatch.delenv("BEJITECH_DEK", raising=False)
    assert ks.load() is None
    exact = bytes(range(32))
    monkeypatch.setenv("BEJITECH_DEK", base64.b64encode(exact).decode())
    assert ks.load() == exact
    ks.save(exact)  # same key: accepted
    with pytest.raises(KeyStoreError):
        ks.save(b"\0" * 32)  # the app can't change the server's key
    monkeypatch.setenv("BEJITECH_DEK", "a-long-random-value-from-the-hosting-service-123")
    assert len(ks.load()) == 32 and ks.load() == ks.load()
    monkeypatch.setenv("BEJITECH_DEK", "short")
    with pytest.raises(KeyStoreError):
        ks.load()
