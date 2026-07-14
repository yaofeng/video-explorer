import struct
import json

MAGIC = b"VDC2"
VERSION = 2
# 4s + 7*I + 4s = 4 + 28 + 4 = 36 bytes
HEADER = struct.Struct("<4sIIIIIII4s")


def write_desc(path: str, desc: dict, small_thumb: bytes, full_thumb: bytes):
    desc_bytes = json.dumps(desc, ensure_ascii=False).encode("utf-8")
    desc_offset = 36
    small_offset = desc_offset + len(desc_bytes)
    full_offset = small_offset + len(small_thumb)
    header = HEADER.pack(
        MAGIC, VERSION, desc_offset, len(desc_bytes),
        small_offset, len(small_thumb), full_offset, len(full_thumb),
        b""
    )
    with open(path, "wb") as f:
        f.write(header)
        f.write(desc_bytes)
        f.write(small_thumb)
        f.write(full_thumb)


def read_desc(path: str):
    with open(path, "rb") as f:
        head = f.read(36)
        magic, version, doff, dlen, soff, slen, foff, flen, _ = HEADER.unpack(head)
        if magic != MAGIC:
            raise ValueError("bad magic")
        f.seek(doff)
        desc = json.loads(f.read(dlen))
        f.seek(soff)
        small_thumb = f.read(slen)
        f.seek(foff)
        full_thumb = f.read(flen)
    return desc, small_thumb, full_thumb
