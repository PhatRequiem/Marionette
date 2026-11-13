# logs: archived guide reports

Extracted from [the active guide](../../../active/current-operation/logs.md) on November 12, 2026. These are prior test reports and development notes, not current configuration or newly executed checks. Undated passages retain their original wording; the extraction date is not a test date. Some passages include operational context necessary to interpret the report.

Keep the SQLite database when updating or reinstalling. Follow [backup and restore](../../../active/current-operation/storage.md#backup-and-restore) rather than copying a live main file without its WAL. Saved records do not restore model context. Synthetic checks cover same-version database restoration and SQL export/import; migration to another database engine is not verified.
