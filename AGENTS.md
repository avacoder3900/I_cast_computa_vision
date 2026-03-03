# Agent Conventions — ICast CV

## Patterns
- Every CRUD function takes a `database` param (Motor `AsyncIOMotorDatabase`)
- Route handlers get DB via `Depends(get_database)`
- Services are module-level functions, not classes (except CameraService)
- All timestamps are UTC `datetime` objects
- Pagination uses `skip` + `limit` query params, default limit=50, max=200

## Gotchas
- `bson.ObjectId` is not JSON-serializable — always convert to `str`
- OpenCV `VideoCapture` blocks — always use `asyncio.to_thread()`
- Motor operations need `await` — forgetting causes silent failures
- `cv2.imread` returns `None` on failure, not an exception
- Pillow `Image.open()` is lazy — call `.load()` or `.save()` to trigger read

## Testing
- Tests use `mongomock_motor` for in-memory MongoDB
- Camera tests mock `cv2.VideoCapture` entirely
- Use `tmp_path` fixture for filesystem tests
- Test client: `httpx.AsyncClient` with `ASGITransport`
