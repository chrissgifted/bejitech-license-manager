# Test results

Run on 18 November 2026 in the development environment:
Linux x86_64 · Python 3.13.18 · SQLite 3.53.1 · PySide6 6.12.0 (Qt offscreen platform).

**Result: 82 passed, 0 failed** (version 1.0.1, re-run 20 Nov 2026; 76 in 1.0.0). Coverage of non-UI code: **92 %** (UI code is exercised by the 5 screen tests but
not counted).

These results come from Linux, not macOS. The same tests run on your Mac via `./packaging/build_macos.sh`
(it stops if any test fails) or `QT_QPA_PLATFORM=offscreen python -m pytest`.

## Other checks performed
| Check | Result |
|---|---|
| `python run.py --self-test` (from source) | All 9 steps passed |
| PyInstaller build **on Linux** using `packaging/bejitech.spec`, then `--self-test` on the frozen build | Built (248 MB folder) and all 9 steps passed. This shows the spec bundles the database files, Qt PDF modules, crypto and keyring correctly. It is **not** the macOS `.app` |
| Demo data + screenshots of each screen (offscreen) | Screens render; see `docs/screenshots/` |
| Delivery note rendered and inspected visually | Layout, key box, clickable link and instructions correct |

## Not tested (needs your Mac)
macOS Keychain storage, building/launching the `.app` and `.dmg`, Gatekeeper behaviour, real printing,
Retina appearance and fonts, performance on M-series hardware.

## Test list
```
integration/test_catalogue.py::test_add_search_edit_archive PASSED
integration/test_catalogue.py::test_new_publisher_created PASSED
integration/test_catalogue.py::test_duplicate_product_rejected PASSED
integration/test_catalogue.py::test_bad_url_rejected PASSED
integration/test_catalogue.py::test_logo_upload PASSED
integration/test_delivery_notes.py::test_pdf_contains_required_content PASSED
integration/test_delivery_notes.py::test_auto_label_when_missing PASSED
integration/test_delivery_notes.py::test_logo_used_and_hash_stored PASSED
integration/test_delivery_notes.py::test_tampered_pdf_is_regenerated PASSED
integration/test_delivery_notes.py::test_new_revision_voids_old PASSED
integration/test_delivery_notes.py::test_email_draft_is_honest PASSED
integration/test_inventory.py::test_key_is_encrypted_at_rest PASSED
integration/test_inventory.py::test_duplicate_key_rejected PASSED
integration/test_inventory.py::test_reference_numbers_sequential PASSED
integration/test_inventory.py::test_usd_purchase_converted PASSED
integration/test_inventory.py::test_states_and_remaining PASSED
integration/test_inventory.py::test_expiry_before_purchase_rejected PASSED
integration/test_inventory.py::test_bulk_add_is_all_or_nothing PASSED
integration/test_inventory.py::test_capacity_cannot_drop_below_allocated PASSED
integration/test_inventory.py::test_low_stock_alerts PASSED
integration/test_inventory.py::test_locked_keys_cannot_be_read PASSED
integration/test_inventory.py::test_update_license_details PASSED
integration/test_inventory.py::test_cannot_make_shared_key_single_customer PASSED
integration/test_inventory.py::test_customer_archive_and_validation PASSED
integration/test_inventory.py::test_change_product_and_licence_type_of_unsold_key PASSED
integration/test_inventory.py::test_product_locked_once_sold PASSED
integration/test_inventory.py::test_change_licence_type_directly PASSED
integration/test_inventory.py::test_licence_type_locked_once_sold PASSED
integration/test_migrations.py::test_fresh_migration_and_seed PASSED
integration/test_migrations.py::test_migrate_is_idempotent PASSED
integration/test_migrations.py::test_orm_models_match_database PASSED
integration/test_migrations.py::test_newer_database_refused PASSED
integration/test_reports_auth_backup.py::test_dashboard_and_profit PASSED
integration/test_reports_auth_backup.py::test_period_filter PASSED
integration/test_reports_auth_backup.py::test_all_reports_export PASSED
integration/test_reports_auth_backup.py::test_login_and_lockout PASSED
integration/test_reports_auth_backup.py::test_weak_password_rejected PASSED
integration/test_reports_auth_backup.py::test_recovery_when_keychain_lost PASSED
integration/test_reports_auth_backup.py::test_change_password PASSED
integration/test_reports_auth_backup.py::test_audit_log_append_only PASSED
integration/test_reports_auth_backup.py::test_backup_verify_restore_roundtrip PASSED
integration/test_reports_auth_backup.py::test_tampered_backup_rejected PASSED
integration/test_sales.py::test_sale_allocates_and_records_everything PASSED
integration/test_sales.py::test_recommendation_prefers_partial_then_fifo PASSED
integration/test_sales.py::test_recommendation_prefers_expiring_soonest PASSED
integration/test_sales.py::test_split_when_no_single_key_is_enough PASSED
integration/test_sales.py::test_oversell_prevented PASSED
integration/test_sales.py::test_database_rejects_oversell_even_if_code_is_bypassed PASSED
integration/test_sales.py::test_failed_sale_rolls_back_completely PASSED
integration/test_sales.py::test_single_customer_key_not_shared PASSED
integration/test_sales.py::test_multi_customer_key_shared PASSED
integration/test_sales.py::test_expired_and_disabled_not_allocated PASSED
integration/test_sales.py::test_discount_and_validation PASSED
integration/test_sales.py::test_confirm_then_cancel_keeps_capacity_used PASSED
integration/test_sales.py::test_cancel_release_only_when_allowed PASSED
integration/test_sales.py::test_concurrent_sales_cannot_oversell PASSED
integration/test_sales.py::test_customer_history PASSED
ui/test_ui_smoke.py::test_every_page_opens PASSED
ui/test_ui_smoke.py::test_product_form_adds_product PASSED
ui/test_ui_smoke.py::test_full_sale_workflow_through_ui PASSED
ui/test_ui_smoke.py::test_reports_tabs PASSED
ui/test_ui_smoke.py::test_settings_save PASSED
ui/test_ui_smoke.py::test_edit_dialog_allows_product_change_until_sold PASSED
ui/test_ui_smoke.py::test_licence_type_field_in_edit_and_add PASSED
unit/test_architecture.py::test_no_qt_outside_ui PASSED
unit/test_misc.py::test_file_keystore_roundtrip PASSED
unit/test_misc.py::test_log_redacts_keys PASSED
unit/test_misc.py::test_self_test_passes PASSED
unit/test_money.py::test_parse_tzs_with_separators PASSED
unit/test_money.py::test_parse_usd_cents PASSED
unit/test_money.py::test_negative_rejected PASSED
unit/test_money.py::test_garbage_rejected PASSED
unit/test_money.py::test_format PASSED
unit/test_money.py::test_usd_to_tzs_conversion_uses_rate PASSED
unit/test_money.py::test_per_unit_cost_rounds PASSED
unit/test_security.py::test_encrypt_roundtrip_and_aad_binding PASSED
unit/test_security.py::test_wrong_key_fails PASSED
unit/test_security.py::test_fingerprint_normalises PASSED
unit/test_security.py::test_dek_check PASSED
unit/test_security.py::test_password_hash PASSED
unit/test_security.py::test_kdf_deterministic_with_same_salt PASSED
unit/test_security.py::test_masking_and_redaction PASSED
```

## Coverage by module
| Module | Coverage |
|---|---|
| src/bejitech/core/__init__.py | 100% |
| src/bejitech/core/dto.py | 99% |
| src/bejitech/core/enums.py | 100% |
| src/bejitech/core/errors.py | 100% |
| src/bejitech/core/money.py | 93% |
| src/bejitech/core/timeutil.py | 81% |
| src/bejitech/db/__init__.py | 100% |
| src/bejitech/db/engine.py | 100% |
| src/bejitech/db/migrations.py | 80% |
| src/bejitech/db/models.py | 100% |
| src/bejitech/db/seed.py | 100% |
| src/bejitech/exports/__init__.py | 100% |
| src/bejitech/exports/csv_export.py | 100% |
| src/bejitech/pdf/__init__.py | 100% |
| src/bejitech/pdf/delivery_note.py | 100% |
| src/bejitech/pdf/report_pdf.py | 97% |
| src/bejitech/pdf/styles.py | 89% |
| src/bejitech/security/__init__.py | 100% |
| src/bejitech/security/crypto.py | 98% |
| src/bejitech/security/keystore.py | 63% |
| src/bejitech/security/masking.py | 100% |
| src/bejitech/security/passwords.py | 100% |
| src/bejitech/services/__init__.py | 100% |
| src/bejitech/services/allocation_service.py | 90% |
| src/bejitech/services/audit_service.py | 78% |
| src/bejitech/services/auth_service.py | 82% |
| src/bejitech/services/backup_service.py | 94% |
| src/bejitech/services/catalogue_service.py | 87% |
| src/bejitech/services/common.py | 100% |
| src/bejitech/services/context.py | 100% |
| src/bejitech/services/customer_service.py | 91% |
| src/bejitech/services/delivery_note_service.py | 88% |
| src/bejitech/services/inventory_service.py | 89% |
| src/bejitech/services/reporting_service.py | 100% |
| src/bejitech/services/sales_service.py | 86% |
| src/bejitech/services/settings_service.py | 93% |
| TOTAL | 92% |
