#!/usr/bin/env python3

import sys

device_path = len(sys.argv) > 1 and sys.argv[1]
if not device_path:
    device_path = input('Enter a block device path: ').strip()
if not device_path:
    print('Aborting: block device path is required')
    sys.exit(1)

sector_size = 512
header_size = 512 * 1024
known_offsets = {
    524288     : 'X',
    786956288  : 'Y',
    1573388288 : 'Z',
    2359820288 : 'C',
    2884108288 : 'E',
    8004132864 : 'F',
}

f = open(device_path, 'rb')
header = f.read(header_size)

intro = b'****PARTINFO****' + b'\0' * 32
if not header.startswith(intro):
    print('FATX partition table not found on', device_path)
    f.close()
    sys.exit(1)

partitions = []
for i in range(14):
    offset = len(intro) + i * 32
    entry = header[offset:offset + 32]
    info = {}
    partitions.append(info)
    info['name'] = entry[0:16].decode().rstrip()
    info['offset'] = int.from_bytes(entry[20:24], 'little') * sector_size
    info['size'] = int.from_bytes(entry[24:28], 'little') * sector_size

    f.seek(info['offset'])
    p_start = f.read(12)
    if p_start.startswith(b'FATX'):
        info['cluster_size'] = int.from_bytes(p_start[8:12], 'little') * sector_size

f.close()

partitions = filter(lambda p: p['name'], partitions)
partitions = sorted(partitions, key=lambda p: p['offset'])

def print_row(values, width=16, width0=24):
    print(''.join([values[i].ljust(width0 if i == 0 else width) for i in range(len(values))]))

print_row(['PARTITION NAME', 'LETTER', 'OFFSET', 'SIZE', 'SIZE MB', 'CLUSTER SIZE'])
print_row(['='*22, '='*14, '='*14, '='*14, '='*14, '='*14])
for p in partitions:
    size_mb = '{} MB'.format(p['size'] // 2**20)
    cluster_size = '{} KB'.format(p['cluster_size'] // 2**10) if 'cluster_size' in p else 'error'
    letter = known_offsets[p['offset']] if p['offset'] in known_offsets else 'G / other'
    print_row([p['name'], letter, str(p['offset']), str(p['size']), size_mb, cluster_size])
