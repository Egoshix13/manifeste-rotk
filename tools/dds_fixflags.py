"""Ajoute le flag DDSD_WIDTH (0x4) absent des DDS ecrits par ForgeLight.
Sans lui, les outils stricts (nvddsinfo, nvdecompress) refusent le fichier."""
import struct, sys, shutil


def fix_flags(src, dst):
    shutil.copyfile(src, dst)
    with open(dst, 'r+b') as fh:
        fh.seek(8)
        flags = struct.unpack('<I', fh.read(4))[0]
        fh.seek(8)
        fh.write(struct.pack('<I', flags | 0x4))
    return flags, flags | 0x4


if __name__ == '__main__':
    old, new = fix_flags(sys.argv[1], sys.argv[2])
    print(f'flags 0x{old:08x} -> 0x{new:08x}  ({sys.argv[2]})')
