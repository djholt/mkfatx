import hashlib
import hmac
import subprocess
import sys

def get_hdd_id(device_path):
    cmd = ['hdparm', '--Istdout', device_path]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError('hdparm exited with non-zero status')
    id_hex = ' '.join(proc.stdout.decode().split('\n')[2:])
    id_bytes = bytes.fromhex(id_hex)
    serial = id_bytes[20:40].rstrip(b' ')
    model = id_bytes[54:94].rstrip(b' ')
    return model, serial

def hash_hdd_pw(key_bytes, model_bytes, serial_bytes):
    h = hmac.new(key_bytes, model_bytes + serial_bytes, hashlib.sha1)
    return h.digest()

def set_hdd_security(device_path, pw_bytes, command):
    pw_hex = pw_bytes.ljust(32, b'\0').hex()
    cmd = ['hdparm', '--security-' + command, 'hex:' + pw_hex, device_path]
    print('Running:', ' '.join(cmd))
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError('hdparm exited with non-zero status')

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('usage: hddlock.py lock device-path hdd-key')
        print('usage: hddlock.py unlock device-path hdd-key')
        print('usage: hddlock.py disable device-path hdd-key')
        sys.exit(1)

    lock_unlock = sys.argv[1]
    device_path = sys.argv[2]
    hdd_key_hex = sys.argv[3]

    model_bytes, serial_bytes = get_hdd_id(device_path)
    hdd_key_bytes = bytes.fromhex(hdd_key_hex)
    hdd_pw_bytes = hash_hdd_pw(hdd_key_bytes, model_bytes, serial_bytes)
    if lock_unlock == 'lock':
        set_hdd_security(device_path, hdd_pw_bytes, 'set-pass')
    if lock_unlock == 'unlock':
        set_hdd_security(device_path, hdd_pw_bytes, 'unlock')
    if lock_unlock == 'disable':
        set_hdd_security(device_path, hdd_pw_bytes, 'disable')
