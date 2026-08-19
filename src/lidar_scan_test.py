import serial
import time

PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0"
BAUD = 115200


def parse_samples(buf):
    points = []
    for i in range(0, len(buf) - 4, 5):
        b = buf[i:i + 5]
        start = b[0] & 0x01
        not_start = (b[0] >> 1) & 0x01
        check = b[1] & 0x01
        if start == not_start or check != 1:
            continue
        quality = b[0] >> 2
        angle_deg = ((b[2] << 7) | (b[1] >> 1)) / 64.0
        distance_mm = (b[3] | (b[4] << 8)) / 4.0
        if 0 <= angle_deg < 360 and 0 < distance_mm <= 8000:
            points.append((angle_deg, distance_mm, quality))
    return points


with serial.Serial(PORT, BAUD, timeout=0.1, write_timeout=0.5, rtscts=False, dsrdtr=False) as ser:
    ser.dtr = False
    ser.rts = False
    time.sleep(1.0)
    ser.reset_input_buffer()
    ser.write(bytes.fromhex("A5 20"))
    ser.flush()
    start = time.monotonic()
    data = bytearray()
    while time.monotonic() - start < 3.0:
        data.extend(ser.read(4096))
    ser.write(bytes.fromhex("A5 25"))
    ser.flush()

best = []
for offset in range(5):
    points = parse_samples(data[offset:])
    if len(points) > len(best):
        best = points

print(f"RAW_BYTES={len(data)}")
print(f"VALID_POINTS={len(best)}")
if best:
    distances = [p[1] for p in best]
    print(f"MIN_MM={min(distances):.1f}")
    print(f"MAX_MM={max(distances):.1f}")
