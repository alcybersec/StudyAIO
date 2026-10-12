# CSIT314 — Week 9: Public-Key Cryptography

## Overview

This week introduces public-key cryptography, a fundamentally different way of designing encryption from the symmetric schemes seen earlier in the course. Symmetric encryption relies on one shared secret key that both parties must possess. Public-key encryption instead uses a key pair: a public key that anyone can use to encrypt a message to you, and a private key that only you hold and use to decrypt. The result is a powerful property — anyone can encrypt to you; only you can decrypt [p.1].

The flagship algorithm covered is RSA, whose security rests on the difficulty of factoring a large number `n = p * q` into its primes [p.1]. In other words, the very act that makes the public key easy to construct — multiplying two large primes — is what makes recovering the private key computationally infeasible. This week walks through the full RSA lifecycle: key generation, encryption, decryption, and a worked toy example that makes the mechanics concrete [p.2][p.3].

## Key Concepts

### Symmetric vs. Public-Key Encryption

Symmetric encryption uses one shared secret key [p.1]. This means both sender and receiver must somehow agree on and protect the same key. Public-key encryption breaks this constraint by using a pair of keys: a public key to encrypt and a private key to decrypt [p.1]. The practical consequence is elegant: anyone can encrypt to you; only you can decrypt [p.1]. Your public key can be shared freely, while the private key never leaves your possession.

### RSA and Its Security Foundation

RSA's security does not come from hiding the algorithm — it comes from a hard mathematical problem. RSA security rests on the difficulty of factoring a large number `n = p * q` into its primes [p.1]. An attacker who sees the public modulus `n` would need to recover the primes `p` and `q` to derive the private key. Multiplying is easy; factoring is not — and this asymmetry is the entire foundation of the scheme [p.1].

### RSA Key Generation

Generating an RSA key pair follows a defined procedure [p.2]:

1. Pick primes `p` and `q` [p.2].
2. Compute `n = p * q` and `phi = (p-1)(q-1)` [p.2].
3. Pick `e` coprime to `phi` [p.2].
4. Compute `d` with `e * d ≡ 1 (mod phi)` — that is, `d` is the multiplicative inverse of `e` modulo `phi` [p.2].
5. Publish the public key `(n, e)`; keep the private key `(n, d)` secret [p.2].

The structure matters: `e` and `d` are inverses mod `phi`, so applying one after the other undoes the effect — but only someone who knows `phi` (and hence `p` and `q`) can compute `d`. This is where the factoring difficulty from [p.1] protects the scheme.

### Encryption and Decryption

Once keys exist, the operations are simple modular exponentiations [p.2]:

- Encrypt a message `m` as `c = m^e mod n` [p.2].
- Decrypt the ciphertext as `m = c^d mod n` [p.2].

The sender uses the recipient's public exponent `e`; the recipient uses their own private exponent `d`. Because `e * d ≡ 1 (mod phi)`, the exponentiations cancel in modular arithmetic and the original message is recovered.

### Worked Toy Example

The lecture demonstrates a complete RSA round trip with deliberately tiny numbers — a toy example, far too small to be secure, but perfect for seeing every step [p.3]:

1. Primes: `p = 3`, `q = 11`, giving `n = 33` and `phi = 20` [p.3].
2. Choose `e = 3`, then `d = 7`, since `3 * 7 = 21 ≡ 1 (mod 20)` [p.3].
3. Public key is `(33, 3)`; private key is `(33, 7)` [p.3].
4. Encrypt `m = 4`: `c = 4^3 mod 33 = 31` [p.3].
5. Decrypt: `31^7 mod 33 = 4`, recovering the original message [p.3].

Tracing this example by hand — especially verifying that `31^7 mod 33 = 4` — is the best way to internalise why the inverse-exponent property makes decryption work.

## Definitions

| Term | Definition |
|---|---|
| Symmetric encryption | Encryption using one shared secret key [p.1] |
| Public-key encryption | Encryption using a pair: a public key to encrypt, a private key to decrypt [p.1] |
| Public key | The key `(n, e)` shared with everyone so anyone can encrypt to you [p.1][p.2] |
| Private key | The key `(n, d)` kept secret so only you can decrypt [p.1][p.2] |
| RSA | A public-key scheme whose security rests on the difficulty of factoring `n = p * q` into its primes [p.1] |
| `n` | The modulus, computed as `n = p * q` [p.2] |
| `phi` | `(p-1)(q-1)`, used to select `e` and compute `d` [p.2] |
| `e` | The public exponent, chosen coprime to `phi` [p.2] |
| `d` | The private exponent satisfying `e * d ≡ 1 (mod phi)` [p.2] |

## Diagrams & Visual Descriptions

The RSA key exchange and message flow can be visualised as follows:

```
        Key Generation                         Message Flow
 -------------------------          ---------------------------------
 p, q primes                      Sender (encrypts):  c = m^e mod n
        |                                 |            [p.2]
 n = p*q,  phi = (p-1)(q-1)   [p.2]           v  (public key n,e)
        |                             Recipient (decrypts): m = c^d mod n
 e coprime to phi; d: e*d ≡ 1 (mod phi) [p.2]   [p.2]
        |
 Public (n,e)   Private (n,d)   [p.2]
```

Anyone may hold the public key `(n, e)` and produce ciphertext, but only the holder of `(n, d)` can invert it — capturing the lecture's point that anyone can encrypt to you; only you can decrypt [p.1].

## Code Examples

No code examples in this lecture.

## Formulas & Algorithms

RSA key generation procedure [p.2]:

```
pick primes p and q
n = p * q
phi = (p-1)(q-1)
pick e coprime to phi
compute d with e * d ≡ 1 (mod phi)
public key (n, e), private key (n, d)
```

Encryption and decryption [p.2]:

```
c = m^e mod n
m = c^d mod n
```

Worked toy example, far too small to be secure [p.3]:

```
p = 3, q = 11
n = 33
phi = 20
e = 3, d = 7  since 3 * 7 = 21 ≡ 1 (mod 20)
Encrypt m = 4: c = 4^3 mod 33 = 31
Decrypt: 31^7 mod 33 = 4
```

Security foundation [p.1]:

```
factoring a large number n = p * q into its primes
```

## Key Takeaways

- The move from one shared key (symmetric) to a key pair (public/private) removes the need to secretly share a key first: anyone can encrypt to you; only you can decrypt [p.1].
- RSA's security is not obscurity — it rests on the difficulty of factoring `n = p * q` into its primes [p.1].
- The private exponent `d` is defined purely by the modular inverse condition `e * d ≡ 1 (mod phi)`, computable only if you know `phi` and hence the primes [p.2].
- Encryption and decryption are the same kind of operation — a modular exponentiation — differing only in which exponent is used [p.2].
- The toy example (`n = 33`) lets you verify every step by hand, but real security requires keys whose factoring is infeasible [p.3].

## Connections

The lecture explicitly contrasts public-key encryption with symmetric encryption and its single shared secret key [p.1], situating this week against the symmetric schemes the course has covered. The contrast the lecture draws — one shared key versus a key pair — is the anchor point for linking this material to that earlier material.

The lecture also leaves implicit the practical scale question: it stresses that its toy example is "far too small to be secure" [p.3], pointing at the factoring hardness of large `n` [p.1] as what separates a teaching example from a real system.

---
*Sources: CSIT314 Week 9 lecture slides (pp. 1–3). Version: 1.*
