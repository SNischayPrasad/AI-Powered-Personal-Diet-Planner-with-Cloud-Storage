# 08 · Cloud storage

## Two kinds of cloud data

| | Cloud database | Cloud object storage |
|---|---|---|
| Holds | **Structured information**: users, profiles, plans, file *metadata* | **Files**: meal images, PDFs, exported plans |
| Model | Tables, rows, columns, relationships | Bucket → key → bytes (+ content type) |
| Operations | Query, filter, join, update in transactions | Put, get and delete whole objects |
| Scales for | Many small records you search | Large blobs you store and serve |
| Here | PostgreSQL / SQLite: `user_files` row | S3 / Supabase Storage / R2 / RustFS / folder: object at `storage_path` |

The project uses **both**. An upload writes the bytes to the bucket and a metadata row to the
database that points at them.

```text
POST /api/upload (multipart, JWT)
   │ 1. read up to MAX_UPLOAD_MB + 1 byte  → 413 if larger
   │ 2. detect the type from magic bytes    → 415 if not JPEG/PNG/WebP/PDF, or if the name disagrees
   │ 3. check the quota (50 files per user) → 403 storage_quota_exceeded
   │ 4. key = users/<user-id>/meal-images/<random-uuid>.png
   ├──► object storage: put(key, bytes, content_type)
   └──► database: INSERT user_files(id, user_id, filename, storage_path=key, …)
            └─ if this fails → storage.delete(key)   (compensating action, no orphans)
```

## What users can do

| Brief | Endpoint | Where the data goes |
|---|---|---|
| Save generated diet plans | `POST /api/generate-plan` | Database (`diet_plans`) |
| Save a plan *as a file* | `POST /api/plans/{id}/save-to-cloud?format=json\|txt` | Object storage `plan-exports/` + metadata |
| Upload demo meal images | `POST /api/upload` | Object storage `meal-images/` (or `documents/` for PDFs) |
| Download / export a plan | `GET /api/plans/{id}/export?format=json\|txt` | Generated from the database on the fly |
| Retrieve stored files | `GET /api/files`, `GET /api/files/{id}/download` | Metadata from the database, bytes from storage |
| Retrieve previous plans | `GET /api/plans`, `GET /api/plans/{id}` | Database |
| Delete a file | `DELETE /api/files/{id}` | Object deleted first, then the metadata row |

## Providers: one interface, several back ends

[`cloud/storage_service.py`](../cloud/storage_service.py) defines a `StorageService`
abstract class with `upload`, `download`, `delete` and `health_check`.

| `STORAGE_PROVIDER` | Class | Use |
|---|---|---|
| `local` (default) | `LocalStorageService` | A folder `data/object_storage/<bucket>/…` that behaves like a bucket. Writes are atomic (temporary file + rename) |
| `s3` | `S3StorageService` (boto3) | AWS S3 (IAM role or keys), Supabase Storage, Cloudflare R2, Backblaze B2, RustFS / MinIO via `S3_ENDPOINT_URL` and `S3_FORCE_PATH_STYLE=true` |

The rest of the app never imports boto3. Switching from the laptop folder to AWS S3 is two
environment variables. Adding Azure Blob Storage would mean one new class.

## Security of stored files

- **Private bucket, no public URLs.** Every download goes through the API, which checks
  `user_files.user_id == current user` first. Other users get 404.
- **Server-generated keys.** The key is `users/<uuid>/<folder>/<random uuid>.<ext>`. The
  uploader's file name is only a sanitised display name, so there is no path traversal
  (`../../etc/passwd`) and names can't be guessed. Keys are validated against a strict
  pattern before any storage call.
- **Content sniffing.** The type is decided by the first bytes: `\x89PNG`, `\xFF\xD8\xFF`,
  `RIFF…WEBP`, `%PDF-`. A renamed `.exe`, an SVG (which can carry scripts), an HTML file
  named `photo.png.html`, or a JPEG named `.png` are all rejected (TC-17).
- **Limits**: `MAX_UPLOAD_MB` (default 4) and `MAX_FILES_PER_USER` (default 50). Both
  control cost and abuse.
- **Downloads** are served with the detected content type, `Content-Disposition` and
  `X-Content-Type-Options: nosniff`.
- **Encryption at rest** is on by default in S3, Supabase and R2. Encryption in transit comes
  from HTTPS to the provider.

## Failure handling (TC-20)

| Situation | Behaviour |
|---|---|
| Bucket unreachable or not writable | 503 `storage_unavailable`; readiness reports `"storage": "unavailable"`; nothing half-saved |
| Upload succeeded, database insert failed | The object is deleted again (compensating transaction) |
| Delete: storage fails | 503 and the metadata row is kept, so the user can retry; no dangling rows |
| Storage back | Works again with no restart |

## Try it

```bash
# After logging in through the UI, or with a token from POST /api/login:
curl -H "Authorization: Bearer $TOKEN" -F "file=@sample_data/images/lunch-thali.png" http://localhost:8000/api/upload
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/files
```

Locally, the object appears under `data/object_storage/diet-planner-files/users/<your-id>/meal-images/`.
With Docker, browse the bucket in the RustFS console at http://localhost:9001.
