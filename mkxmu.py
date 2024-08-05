#!/usr/bin/env python3

import math
import sys
import time

sector_size = 4096
cluster_size = 16 * 1024 # 16 KB

if len(sys.argv) != 3:
    print('usage: mkxmu.py size-in-mb output-file-path')
    sys.exit(1)

size_mb   = sys.argv[1]
file_path = sys.argv[2]

mem_size = int(size_mb) * 2**20

num_clusters = mem_size // cluster_size
chain_entry_size = 2 if num_clusters < 65525 else 4
chain_table_size = num_clusters * chain_entry_size
chain_table_size = math.ceil(chain_table_size / 4096) * 4096
header_size = 4 + 4 + 4 + 2 + 4 + 0xfee + chain_table_size + cluster_size

out_bytes = b'FATX'
out_bytes += int(time.time()).to_bytes(4, 'little')
out_bytes += (cluster_size // sector_size).to_bytes(4, 'little')
out_bytes += (0x1).to_bytes(2, 'little')
out_bytes += (0x0).to_bytes(4, 'little')
out_bytes += bytearray([0xff] * 0xfee)

if chain_entry_size == 2:
    out_bytes += (0xfff8).to_bytes(2, 'little')
    out_bytes += (0xffff).to_bytes(2, 'little')
else:
    out_bytes += (0xfffffff8).to_bytes(4, 'little')
    out_bytes += (0xffffffff).to_bytes(4, 'little')

out_bytes += bytearray(chain_table_size - chain_entry_size * 2)
out_bytes += bytearray([0xff] * cluster_size)

print('Writing to file...')
f = open(file_path, 'wb')
f.write(out_bytes)

bytes_remaining = mem_size - header_size
while bytes_remaining > cluster_size:
    f.write(b'\0' * cluster_size)
    bytes_remaining -= cluster_size
f.write(b'\0' * bytes_remaining)
f.close()
print('Done!')
