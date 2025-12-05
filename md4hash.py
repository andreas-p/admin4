# The Admin4 Project
# (c) 2025 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

# replacement for haslib/openssl MD4


from binascii import hexlify

BLOCKSIZE=64
WORDSIZE=4
MASK=0xFFFFFFFF

class MD4Hash:
  # RFC 1320
  def __init__(self, data: bytes):
    def fn_f(x, y, z):
      return (x & y) | (~x & z)
    def fn_g(x, y, z):
      return (x & y) | (x & z) | (y & z)
    def fn_h(x, y, z):
      return x ^ y ^ z
    def rotateLeft(x, n):
      return (x << n) | (x >> (32 - n))

    padding = b"\x80" + b"\x00" * 63
    lenBytes = len(data)
    index = lenBytes % BLOCKSIZE
    data += padding[0:56 - index] if index < 56 else padding[0:120 - index]
    data += (lenBytes*8).to_bytes(8, byteorder='little')

    A=0x67452301
    B=0xefcdab89
    C=0x98badcfe
    D=0x10325476

    for i in range(0, lenBytes, WORDSIZE * 16):
      blocks = [int.from_bytes(data[i + j:i + j + WORDSIZE], 'little') for j in range(0, BLOCKSIZE, WORDSIZE)] # 16 32-bit blocks

      AA = A
      BB = B
      CC = C
      DD = D

      round1Steps = (3, 7, 11, 19)
      for j in range(0, 16, 4):
        A = rotateLeft((A + fn_f(B, C, D) + blocks[j]) & MASK, round1Steps[j % 4])
        D = rotateLeft((D + fn_f(A, B, C) + blocks[j + 1]) & MASK, round1Steps[(j + 1) % 4])
        C = rotateLeft((C + fn_f(D, A, B) + blocks[j + 2]) & MASK, round1Steps[(j + 2) % 4])
        B = rotateLeft((B + fn_f(C, D, A) + blocks[j + 3]) & MASK, round1Steps[(j + 3) % 4])

      for j in range(4):
        A = rotateLeft((A + fn_g(B, C, D) + blocks[j] + 0x5a827999)  & MASK, 3)
        D = rotateLeft((D + fn_g(A, B, C) + blocks[j + 4] + 0x5a827999) & MASK, 5)
        C = rotateLeft((C + fn_g(D, A, B) + blocks[j + 8] + 0x5a827999) & MASK, 9)
        B = rotateLeft((B + fn_g(C, D, A) + blocks[j + 12] + 0x5a827999) & MASK, 13)

      round3Blocks = ((0, 8, 4, 12), (2, 10, 6, 14), (1, 9, 5, 13), (3, 11, 7, 15))
      for j in range(4):
        A = rotateLeft((A + fn_h(B, C, D) + blocks[round3Blocks[j][0]] + 0x6ed9eba1) & MASK, 3)
        D = rotateLeft((D + fn_h(A, B, C) + blocks[round3Blocks[j][1]] + 0x6ed9eba1) & MASK, 9)
        C = rotateLeft((C + fn_h(D, A, B) + blocks[round3Blocks[j][2]] + 0x6ed9eba1) & MASK, 11)
        B = rotateLeft((B + fn_h(C, D, A) + blocks[round3Blocks[j][3]] + 0x6ed9eba1) & MASK, 15)

      A = (A + AA) & MASK
      B = (B + BB) & MASK
      C = (C + CC) & MASK
      D = (D + DD) & MASK

    self._digest=A.to_bytes(4, byteorder='little') + B.to_bytes(4, byteorder='little') + C.to_bytes(4, byteorder='little') + D.to_bytes(4, byteorder='little')

  def digest(self):
    return self._digest;

  def hexdigest(self):
    return hexlify(self._digest).decode("utf-8")
  