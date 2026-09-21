import pathlib
import struct

root = pathlib.Path(__file__).resolve().parents[3]
path = root / 'Saved/Crashes/UECC-Windows-5843FF024B103EDA671B6DB337EE3F28_0002/UEMinidump.dmp'
data = path.read_bytes()
count, directory = struct.unpack_from('<II', data, 8)
for index in range(count):
    kind, size, rva = struct.unpack_from('<III', data, directory + index * 12)
    if kind == 4:
        for module_index in range(struct.unpack_from('<I', data, rva)[0]):
            offset = rva + 4 + module_index * 108
            base, image_size, checksum, timestamp, name_rva = struct.unpack_from('<QIIII', data, offset)
            length = struct.unpack_from('<I', data, name_rva)[0]
            name = data[name_rva + 4:name_rva + 4 + length].decode('utf-16-le')
            if any(term in name.lower() for term in ('dxgi', 'nvwg', 'overlay', 'rtss', 'nahimic', 'hook', 'nvspcap', 'discord', 'reshade')):
                print(hex(base), hex(image_size), name)
    if kind == 6:
        thread, _ = struct.unpack_from('<II', data, rva)
        code, flags, record, address = struct.unpack_from('<IIQQ', data, rva + 8)
        access, target = struct.unpack_from('<QQ', data, rva + 40)
        print('EXCEPTION', hex(code), 'THREAD', thread, 'IP', hex(address), 'ACCESS', access, 'TARGET', hex(target))
