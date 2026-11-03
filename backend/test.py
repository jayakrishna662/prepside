import uuid

from app.api.deps import TEMP_USER_ID
from app.services.vision import build_visual_chunks

with open("community_solar_report.pdf", "rb") as f:
    data = f.read()

doc_id = uuid.uuid4()
chunks = build_visual_chunks(
    data,
    TEMP_USER_ID,
    doc_id,
    on_progress=lambda done, total: print(f"described {done} of {total} pages"),
)

print(f"\n{len(chunks)} picture chunks")
for c in chunks:
    print(f"\npage {c.page} | {c.kind} | {c.asset_path}")
    print(c.content[:200])

print(f"\nTest pictures are in: storage/{TEMP_USER_ID}/{doc_id}  (delete this folder after checking)")