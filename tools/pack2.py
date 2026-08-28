"""Lecteur minimal d'archives ForgeLight .pack2 (Daybreak / H1Z1).

Format (little-endian) :
  header : 'PAK\x01' | u32 asset_count | u64 file_length | u64 map_offset | u64 ?
  map    : asset_count * 32 octets -> u64 name_hash | u64 offset | u64 size | u32 zipped | u32 crc32
  data   : si zipped, le bloc commence par A1 B2 C3 D4 (BE) + u32 BE taille decompressee + zlib
"""
import struct, sys, zlib, os

ENTRY = struct.Struct('<QQQII')
ZIP_MAGIC = b'\xa1\xb2\xc3\xd4'


class Pack2:
    def __init__(self, path):
        self.path = path
        self.fh = open(path, 'rb')
        magic, count, length, map_off, _pad = struct.unpack('<4sIQQQ', self.fh.read(32))
        if magic != b'PAK\x01':
            raise ValueError(f'{path}: magic inattendu {magic!r}')
        self.count, self.length, self.map_offset = count, length, map_off
        self.fh.seek(map_off)
        raw = self.fh.read(count * ENTRY.size)
        self.assets = [ENTRY.unpack_from(raw, i * ENTRY.size) for i in range(count)]

    def read(self, entry):
        _h, off, size, zipped, _crc = entry
        self.fh.seek(off)
        blob = self.fh.read(size)
        if zipped and blob[:4] == ZIP_MAGIC:
            return zlib.decompress(blob[8:])
        return blob

    def close(self):
        self.fh.close()


# Hash des noms dans les .pack2 : CRC-64 "Jones" (poly reflechi 0x95AC9329AC4BC9B5),
# init et xorout = 0xFFFFFFFFFFFFFFFF, calcule sur le nom de fichier en MAJUSCULES.
# (verifie empiriquement contre les noms trouves en clair dans les assets)
_POLY = 0x95AC9329AC4BC9B5
_TABLE = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ _POLY if _c & 1 else _c >> 1
    _TABLE.append(_c)


def crc64(name):
    crc = 0xFFFFFFFFFFFFFFFF
    for b in name.upper().encode('utf-8'):
        crc = (crc >> 8) ^ _TABLE[(crc ^ b) & 0xFF]
    return crc ^ 0xFFFFFFFFFFFFFFFF


if __name__ == '__main__':
    p = Pack2(sys.argv[1])
    print(f'{os.path.basename(p.path)} : {p.count} assets, map @ {p.map_offset}')
    for e in p.assets[:5]:
        print(f'  hash={e[0]:016x} off={e[1]} size={e[2]} zip={e[3]} crc32={e[4]:08x}')
    p.close()
