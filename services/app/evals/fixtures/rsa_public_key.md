# CSIT314 — Week 9: Public-Key Cryptography and RSA

## Overview

Public-key cryptography splits the key in two. RSA is the worked case, with a toy example whose numbers the lecture computes in full.

## Key Concepts

### Two keys

Symmetric encryption uses one shared secret key. Public-key encryption uses a pair: a public key to encrypt and a private key to decrypt. Anyone can encrypt to you; only you can decrypt.

### RSA

RSA's security rests on the difficulty of factoring a large number n = p * q into its primes. Generate keys by picking primes p and q, computing n = p * q and phi = (p-1)(q-1), picking e coprime to phi, and computing d with e * d ≡ 1 (mod phi). The public key is (n, e) and the private key is (n, d).

### Toy example

The lecture's example is far too small to be secure: p = 3, q = 11, n = 33, phi = 20, e = 3, d = 7 since 3 * 7 = 21 ≡ 1 (mod 20). Encrypting m = 4 gives c = 4^3 mod 33 = 31, and 31^7 mod 33 = 4 recovers it.

## Definitions

| Term | Definition |
|---|---|
| Public key | Shared openly; used to encrypt |
| Private key | Kept secret; used to decrypt |
| phi | (p-1)(q-1) |
| Coprime | Sharing no common factor other than 1 |

## Diagrams & Visual Descriptions

No diagrams in this lecture.

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

```
n = p * q          phi = (p-1)(q-1)
e coprime to phi   e * d ≡ 1 (mod phi)
encrypt: c = m^e mod n
decrypt: m = c^d mod n
toy: p=3 q=11 n=33 phi=20 e=3 d=7; m=4 -> c=4^3 mod 33 = 31; 31^7 mod 33 = 4
```

## Key Takeaways

- Public key encrypts, private key decrypts.
- RSA relies on the difficulty of factoring n.
- The toy numbers are for arithmetic practice, not security.

## Connections

This lecture does not link to other material, and no other weeks were available to compare against.

---
*Sources: rsa_public_key.pdf. Version: 1.*
