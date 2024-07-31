#!/usr/bin/env python3

import json
import math
import plistlib
import re
import subprocess
import sys
import time

device_path = len(sys.argv) > 1 and sys.argv[1]
if not device_path:
    device_path = input('Enter a block device path: ').strip()
if not device_path:
    print('Aborting: block device path is required')
    sys.exit(1)

try:
    if sys.platform == 'darwin':
        if re.search('s[0-9]+$', device_path):
            raise RuntimeError('block device must not be a partition')
        cmd = ['diskutil', 'list', '-plist', device_path]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError('diskutil exited with non-zero status')
        data = plistlib.loads(proc.stdout)
        disks = filter(lambda d: d['DeviceIdentifier'] == data['WholeDisks'][0], data['AllDisksAndPartitions'])
        device_size = list(disks)[0]['Size']
    elif sys.platform == 'linux':
        if re.search('[0-9]+$', device_path):
            raise RuntimeError('block device must not be a partition')
        cmd = ['lsblk', '-Jb', device_path]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError('lsblk exited with non-zero status')
        data = json.loads(proc.stdout)
        device_size = data['blockdevices'][0]['size']
    else:
        raise RuntimeError('currently only Linux and macOS are supported')
except Exception as e:
    print('Aborting: could not determine block device size:', e)
    sys.exit(1)

if device_size < 7*2**30:
    print('Aborting: block device size abnormally small ({} bytes)'.format(device_size))
    sys.exit(1)

if input('Write FATX filesystem to block device {}, size {} MB? (y/n) '.format(device_path, device_size // 2**20)) != 'y':
    print('Aborting: canceled')
    sys.exit(1)

sector_size = 512
header_size = 512 * 1024 # 512 KB
partition_sizes = [
    750 * 1024 * 1024,   # x: 750 MB
    750 * 1024 * 1024,   # y: 750 MB
    750 * 1024 * 1024,   # z: 750 MB
    500 * 1024 * 1024,   # c: 500 MB
    10000048 * 512,      # e: ~4882 MB
    0,                   # f: remaining space, divided evenly
    0                    # g: remaining space, divided evenly
]
num_partitions = len(partition_sizes)

partition_names = [
    'XBOX GAME SWAP 1', # x
    'XBOX GAME SWAP 2', # y
    'XBOX GAME SWAP 3', # z
    'XBOX SYSTEM',      # c
    'XBOX DATA',        # e
    'XBOX F',           # f
    'XBOX G'            # g
]

partition_table_order = [4, 3, 0, 1, 2, 5, 6]
divided_size = (device_size - header_size - sum(partition_sizes)) // (sector_size * 2) * sector_size
partition_sizes[-2] = divided_size
partition_sizes[-1] = divided_size

partition_offsets = [header_size]
for i in range(num_partitions - 1):
    offset = partition_sizes[i] + partition_offsets[-1]
    partition_offsets.append(offset)

cluster_sizes = []
for i in range(num_partitions):
    p_size = partition_sizes[i]
    p_size_gb = p_size // 2**30
    if p_size_gb > 500:
        c_size = 64 * 1024 # 64 KB
    elif p_size_gb > 250:
        c_size = 32 * 1024 # 32 KB
    else:
        c_size = 16 * 1024 # 16 KB
    cluster_sizes.append(c_size)

chain_entry_sizes = []
chain_table_sizes = []
for i in range(num_partitions):
    p_size = partition_sizes[i]
    cluster_size = cluster_sizes[i]
    num_clusters = p_size // cluster_size
    entry_size = 2 if num_clusters < 65525 else 4
    t_size = num_clusters * entry_size
    t_size = math.ceil(t_size / 4096) * 4096
    chain_entry_sizes.append(entry_size)
    chain_table_sizes.append(t_size)

partition_header_sizes = []
for i in range(num_partitions):
    t_size = chain_table_sizes[i]
    cluster_size = cluster_sizes[i]
    p_header_size = 4 + 4 + 4 + 2 + 4 + 0xfee + t_size + cluster_size
    partition_header_sizes.append(p_header_size)

# build partition table
out_bytes = b'****PARTINFO****'
out_bytes += bytearray(32)
for i in partition_table_order:
    p_name   = partition_names[i].ljust(16)
    p_offset = partition_offsets[i] // sector_size
    p_size   = partition_sizes[i] // sector_size
    out_bytes += p_name.encode('utf-8')
    out_bytes += (0x80000000).to_bytes(4, 'little')
    out_bytes += p_offset.to_bytes(4, 'little')
    out_bytes += p_size.to_bytes(4, 'little')
    out_bytes += (0x0).to_bytes(4, 'little')
for i in range(14 - num_partitions):
    out_bytes += b''.ljust(16)
    out_bytes += bytearray(16)

# build remaining header
out_bytes += bytearray(0x600 - len(out_bytes))
out_bytes += b'BRFR'
out_bytes += bytearray(header_size - len(out_bytes))

# open device for writing
f = open(device_path, 'wb')

# write partition table
print('Writing to device...')
f.seek(0)
f.write(out_bytes)

# build partitions
for i in range(num_partitions):
    out_bytes = b'FATX'
    out_bytes += int(time.time()).to_bytes(4, 'little')
    out_bytes += (cluster_sizes[i] // sector_size).to_bytes(4, 'little')
    out_bytes += (0x1).to_bytes(2, 'little')
    out_bytes += (0x0).to_bytes(4, 'little')
    out_bytes += bytearray([0xff] * 0xfee)
    if chain_entry_sizes[i] == 2:
        out_bytes += (0xfff8).to_bytes(2, 'little')
        out_bytes += (0xffff).to_bytes(2, 'little')
    else:
        out_bytes += (0xfffffff8).to_bytes(4, 'little')
        out_bytes += (0xffffffff).to_bytes(4, 'little')
    out_bytes += bytearray(chain_table_sizes[i] - chain_entry_sizes[i] * 2)
    out_bytes += bytearray([0xff] * cluster_sizes[i])

    # write partition
    f.seek(partition_offsets[i])
    f.write(out_bytes)

# write a zero at the end of the output file
# to avoid truncating all trailing zeros
f.seek(device_size - 1)
f.write(b'\0')
f.close()
print('Done!')
