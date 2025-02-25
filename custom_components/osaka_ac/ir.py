# resources
# https://gist.github.com/mildsunrise/1d576669b63a260d2cff35fda63ec0b5
# https://github.com/zeroflow/ESPAircon
# https://github.com/lukasgabriel/DL_smart_aircon
# https://github.com/Astro1247/osaka_integration/tree/main

import json
import io
import base64
from bisect import bisect
from struct import pack, unpack

def decode_ir(code: str) -> list[int]:
	'''
	Decodes an IR code string from a Tuya blaster.
	Returns the IR signal as a list of µs durations,
	with the first duration belonging to a high state.
	'''
	payload = base64.decodebytes(code.encode('ascii'))
	payload = decompress(io.BytesIO(payload))

	signal = []
	while payload:
		assert len(payload) >= 2, \
			f'garbage in decompressed payload: {payload.hex()}'
		signal.append(unpack('<H', payload[:2])[0])
		payload = payload[2:]
	return signal

def encode_ir(signal: list[int], compression_level=2) -> str:
	'''
	Encodes an IR signal (see `decode_ir`)
	into an IR code string for a Tuya blaster.
	'''
	payload = b''.join(pack('<H', t) for t in signal)
	compress(out := io.BytesIO(), payload, compression_level)
	payload = out.getvalue()
	return base64.encodebytes(payload).decode('ascii').replace('\n', '')


# DECOMPRESSION

def decompress(inf: io.FileIO) -> bytes:
	'''
	Reads a "Tuya stream" from a binary file,
	and returns the decompressed byte string.
	'''
	out = bytearray()

	while (header := inf.read(1)):
		L, D = header[0] >> 5, header[0] & 0b11111
		if not L:
			# literal block
			L = D + 1
			data = inf.read(L)
			assert len(data) == L
		else:
			# length-distance pair block
			if L == 7:
				L += inf.read(1)[0]
			L += 2
			D = (D << 8 | inf.read(1)[0]) + 1
			data = bytearray()
			while len(data) < L:
				data.extend(out[-D:][:L-len(data)])
		out.extend(data)

	return bytes(out)


# COMPRESSION

def emit_literal_blocks(out: io.FileIO, data: bytes):
	for i in range(0, len(data), 32):
		emit_literal_block(out, data[i:i+32])

def emit_literal_block(out: io.FileIO, data: bytes):
	length = len(data) - 1
	assert 0 <= length < (1 << 5)
	out.write(bytes([length]))
	out.write(data)

def emit_distance_block(out: io.FileIO, length: int, distance: int):
	distance -= 1
	assert 0 <= distance < (1 << 13)
	length -= 2
	assert length > 0
	block = bytearray()
	if length >= 7:
		assert length - 7 < (1 << 8)
		block.append(length - 7)
		length = 7
	block.insert(0, length << 5 | distance >> 8)
	block.append(distance & 0xFF)
	out.write(block)

def compress(out: io.FileIO, data: bytes, level=2):
	'''
	Takes a byte string and outputs a compressed "Tuya stream".

	Implemented compression levels:
	0 - copy over (no compression, 3.1% overhead)
	1 - eagerly use first length-distance pair found (linear)
	2 - eagerly use best length-distance pair found
	3 - optimal compression (n^3)
	'''
	if level == 0:
		return emit_literal_blocks(out, data)

	W = 2**13 # window size
	L = 255+9 # maximum length
	distance_candidates = lambda: range(1, min(pos, W) + 1)

	def find_length_for_distance(start: int) -> int:
		length = 0
		limit = min(L, len(data) - pos)
		while length < limit and data[pos + length] == data[start + length]:
			length += 1
		return length
	find_length_candidates = lambda: \
		( (find_length_for_distance(pos - d), d) for d in distance_candidates() )
	find_length_cheap = lambda: \
		next((c for c in find_length_candidates() if c[0] >= 3), None)
	find_length_max = lambda: \
		max(find_length_candidates(), key=lambda c: (c[0], -c[1]), default=None)

	if level >= 2:
		suffixes = []; next_pos = 0
		key = lambda n: data[n:]
		find_idx = lambda n: bisect(suffixes, key(n), key=key)
		def distance_candidates():
			nonlocal next_pos
			while next_pos <= pos:
				if len(suffixes) == W:
					suffixes.pop(find_idx(next_pos - W))
				suffixes.insert(idx := find_idx(next_pos), next_pos)
				next_pos += 1
			idxs = (idx+i for i in (+1,-1)) # try +1 first
			return (pos - suffixes[i] for i in idxs if 0 <= i < len(suffixes))

	if level <= 2:
		find_length = { 1: find_length_cheap, 2: find_length_max }[level]
		block_start = pos = 0
		while pos < len(data):
			if (c := find_length()) and c[0] >= 3:
				emit_literal_blocks(out, data[block_start:pos])
				emit_distance_block(out, c[0], c[1])
				pos += c[0]
				block_start = pos
			else:
				pos += 1
		emit_literal_blocks(out, data[block_start:pos])
		return

	# use topological sort to find shortest path
	predecessors = [(0, None, None)] + [None] * len(data)
	def put_edge(cost, length, distance):
		npos = pos + length
		cost += predecessors[pos][0]
		current = predecessors[npos]
		if not current or cost < current[0]:
			predecessors[npos] = cost, length, distance
	for pos in range(len(data)):
		if c := find_length_max():
			for l in range(3, c[0] + 1):
				put_edge(2 if l < 9 else 3, l, c[1])
		for l in range(1, min(32, len(data) - pos) + 1):
			put_edge(1 + l, l, 0)

	# reconstruct path, emit blocks
	blocks = []; pos = len(data)
	while pos > 0:
		_, length, distance = predecessors[pos]
		pos -= length
		blocks.append((pos, length, distance))
	for pos, length, distance in reversed(blocks):
		if not distance:
			emit_literal_block(out, data[pos:pos + length])
		else:
			emit_distance_block(out, length, distance)

def reverse_bits(n):
    result = 0
    for i in range(8):
        result  <<= 1
        result |= n & 1
        n >>= 1
    return result

def create_message(power: bool, temp: int, mode: int, fan:int, timer: bool, timer_val: int, unit_f: bool):
    buf = 0x12000000

    if unit_f:
        assert 61 <= temp <= 89
        buf |= reverse_bits(temp)
    else:
        assert 16 <= temp <= 32
        temp -= 16
        buf |= reverse_bits(temp)

    buf |= reverse_bits(timer_val) << 8

    if power:
        buf |= 0x1 << 8
    if timer:
        buf |= 0x1 << 9
    if unit_f:
        buf |= 0x1 << 10

    if (mode == 8 or mode == 2 or mode == 1):
        buf |= mode << 16
    else:
        buf |= 0x8 << 16

    if fan in [4, 2, 1]:
        buf |= fan << 20
    else:
        buf |= 0x2 << 20

    return buf

def nec_to_raw(ir_data):
    raw_data = []

    # Leader pulse (9ms) and space (4.5ms)
    raw_data.append(9000)  # Leader pulse
    raw_data.append(4500)  # Lspace

    # Convert the data into bits
    for i in range(32):
        bit = (ir_data >> (31 - i)) & 1
        if bit == 1:
            raw_data.append(560)  # Logic 1: 560us pulse
            raw_data.append(1690)  # Logic 1: 1690us space
        else:
            raw_data.append(560)   # Logic 0: 560us pulse
            raw_data.append(560)   # Logic 0: 560us space

    # Stop bit (560us pulse, 560us space)
    raw_data.append(560)   # Logic 0: 560us pulse
    raw_data.append(560)   # Logic 0: 560us space

    return raw_data

# pac_data = create_message(
#     power=True,   # true or false
#     temp=16,      # 16-32 or 61-89
#     mode=8,       # 1=fan, 2=dehumidify, 8=aircon
#     fan=1,        # 1=high, 2=medium, 4=low
#     timer=False,  # true or false
#     timer_val=0,  # 0-12
#     unit_f=False, # true or false (fahrenheit or celsius)
# )
# raw_ir_timings = nec_to_raw(pac_data)
# tuya_code = encode_ir(raw_ir_timings)

# print(pac_data)
# print(raw_ir_timings)
# print(tuya_code)