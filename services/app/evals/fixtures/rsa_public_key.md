# CSIT314 — Week 9: Public-Key Cryptography

## Overview

For most of the history of cryptography, encryption was *symmetric*: the same secret key was used to both encrypt and decrypt a message. This works well once two parties share a key, but it creates a fundamental bootstrap problem — how do you securely get that shared secret to your counterpart in the first place, especially over a network where eavesdroppers may be listening? Public-key cryptography, introduced this week, solves this elegantly by splitting the single key into a pair: a **public key**, which anyone may use to encrypt messages to you, and a **private key**, which only you possess and which is needed to decrypt them.

The flagship algorithm studied here is **RSA**, whose security rests on a beautiful asymmetry in mathematics: multiplying two large prime numbers together is fast, but factoring the result back into its primes is computationally infeasible when the primes are large enough. This week covers how an RSA key pair is generated, how encryption and decryption are performed, and works through a small "toy" example to make the arithmetic concrete — while stressing that toy-sized parameters are far too small for real security.

## Key Concepts

### Symmetric vs. Public-Key Encryption

Symmetric encryption relies on **one shared secret key**: both sender and receiver must hold the same key. This is efficient, but key distribution is its Achilles' heel — any channel used to share the key is also a channel an attacker might intercept.

Public-key encryption breaks this dependency by using a **key pair**:

- The **public key** is distributed openly; anyone can use it to encrypt a message to the key's owner.
- The **private key** is kept secret; only the owner can decrypt messages encrypted with the matching public key.

The consequence is powerful: anyone can encrypt *to* you, but only *you* can decrypt. There is no shared secret to exchange beforehand, which is exactly what makes public-key cryptography the foundation of secure communication between parties who have never met.

### RSA: The Core Idea

RSA's security rests on the **difficulty of factoring a large number** $n = p \times q$ into its prime factors. Multiplying primes is easy; reversing the multiplication is believed to be computationally infeasible for sufficiently large $p$ and $q$. Every piece of the RSA machinery below is built on top of this hardness assumption — an attacker who could factor $n$ could recover the private key from the public key.

### RSA Key Generation

Generating a key pair follows a precise procedure:

1. Pick two primes $p$ and $q$.
2. Compute $n = p \times q$.
3. Compute $\varphi = (p-1)(q-1)$ (Euler's totient of $n$).
4. Pick $e$ coprime to $\varphi$ (so that no factor is shared, guaranteeing a modular inverse exists).
5. Compute $d$ such that $e \cdot d \equiv 1 \pmod{\varphi}$ — i.e., $d$ is the modular multiplicative inverse of $e$ mod $\varphi$.

The **public key** is the pair $(n, e)$ and is published. The **private key** is the pair $(n, d)$ and is kept secret. Note that $q$ and $\varphi$ themselves must remain secret — knowing $\varphi$ would let anyone derive $d$ from the public $e$.

### Encryption and Decryption

With a public key $(n, e)$, a sender encrypts a message $m$ as:

$$c = m^e \bmod n$$

The receiver, holding $(n, d)$, recovers the message:

$$m = c^d \bmod n$$

The reason this round-trips correctly is the modular inverse relationship between $e$ and $d$: raising to $e$ and then to $d$ effectively applies an exponent of $e \cdot d \equiv 1 \pmod{\varphi}$, which "undoes" the exponentiation modulo $n$. Security comes from the fact that an eavesdropper who sees $c$, $n$, and $e$ cannot compute $d$ without factoring $n$.

### A Toy Example

The lecture works a fully worked example, explicitly flagged as *far too small to be secure* — its purpose is to make the arithmetic checkable by hand.

- Primes: $p = 3$, $q = 11$
- Modulus: $n = 3 \times 11 = 33$
- Totient: $\varphi = (3-1)(11-1) = 20$
- Public exponent: $e = 3$ (coprime to 20)
- Private exponent: $d = 7$, since $3 \times 7 = 21 \equiv 1 \pmod{20}$

Public key: $(33, 3)$; private key: $(33, 7)$.

**Encrypt** $m = 4$:

$$c = 4^3 \bmod 33 = 64 \bmod 33 = 31$$

**Decrypt** $c = 31$:

$$m = 31^7 \bmod 33 = 4$$

The message comes back intact, demonstrating the full cycle. In practice, $p$ and $q$ must be hundreds of digits long so that factoring $n$ is beyond any feasible computation — with $n = 33$, an attacker factors it instantly and recovers everything.

## Definitions

| Term | Definition |
|---|---|
| Symmetric encryption | Encryption using a single shared secret key for both encryption and decryption. |
| Public-key encryption | Encryption using a key pair: a public key to encrypt, a private key to decrypt. |
| Public key | The openly distributed half of the pair, $(n, e)$ in RSA; anyone may use it to encrypt to the owner. |
| Private key | The secret half of the pair, $(n, d)$ in RSA; only the owner can decrypt with it. |
| RSA | A public-key cryptosystem whose security rests on the difficulty of factoring $n = p \times q$ into its primes. |
| $n$ (modulus) | The product of the two secret primes $p$ and $q$; part of both public and private keys. |
| $\varphi$ (totient) | $(p-1)(q-1)$; used to derive the private exponent and must be kept secret. |
| $e$ (public exponent) | An integer coprime to $\varphi$, used for encryption. |
| $d$ (private exponent) | The modular inverse of $e$ modulo $\varphi$; used for decryption. |
| Coprime | Sharing no common factors (other than 1); required of $e$ relative to $\varphi$ so the inverse $d$ exists. |

## Diagrams & Visual Descriptions

**Public-key message flow:**

```
        Alice (sender)                          Bob (receiver)
        --------------                          -------------
   message m                       public key (n,e) available to anyone
        |                                      ^
        |  fetches Bob's public key (n,e)      |
        +------------------------------------->|
        |
        |  encrypt: c = m^e mod n
        |
        |            ciphertext c
        +--------------------------------------------> c arrives
                                                       |
                                                       | decrypt: m = c^d mod n
                                                       v
                                                   message m
                                          (private key (n,d) never leaves Bob)
```

The key insight the diagram shows: the public key travels openly and the ciphertext travels over an insecure channel, yet only Bob's private key — which never needs to be transmitted — can undo the encryption.

## Code Examples

No code examples in this lecture. (The toy example above is arithmetic rather than code, but it maps directly to an implementation: modular exponentiation for encrypt/decrypt and a modular-inverse computation for finding $d$.)

## Formulas & Algorithms

**Key generation algorithm:**

1. Choose primes $p$, $q$
2. $n = p \cdot q$
3. $\varphi = (p-1)(q-1)$
4. Choose $e$ coprime to $\varphi$
5. Find $d$ with $e \cdot d \equiv 1 \pmod{\varphi}$
6. Public key: $(n, e)$ — Private key: $(n, d)$

**Encryption / Decryption:**

$$c = m^e \bmod n \qquad\qquad m = c^d \bmod n$$

**Worked example values:** $p=3$, $q=11$, $n=33$, $\varphi=20$, $e=3$, $d=7$ (since $3 \cdot 7 = 21 \equiv 1 \bmod 20$); $m=4 \rightarrow c = 4^3 \bmod 33 = 31 \rightarrow 31^7 \bmod 33 = 4$.

## Key Takeaways

- Public-key cryptography eliminates the key-distribution problem of symmetric encryption: anyone can encrypt to you with your public key, but only your private key can decrypt.
- RSA's security is founded on a one-way computational asymmetry — multiplying primes is easy, factoring their product is not.
- Key generation has strict requirements: $e$ must be coprime to $\varphi$, and $d$ is its modular inverse mod $\varphi$; leaking $\varphi$ (or the primes) destroys security.
- Encryption and decryption are the same operation with different exponents: raise to $e$ with the public key, to $d$ with the private key, both mod $n$.
- Toy parameters (like $n = 33$) illustrate the mechanics but offer zero security — real security demands primes so large that factoring $n$ is infeasible.

## Connections

Within this lecture itself, public-key encryption is presented directly against symmetric encryption and its shared-secret problem, framing the two as complementary approaches to the same goal of confidential communication. The lecture also points beyond pure encryption: the key-generation step requires choosing large primes and computing modular inverses, grounding the scheme in number-theoretic machinery that the course treats as a prerequisite for understanding *why* factoring resistance matters.

No other weeks were named in this lecture, so no cross-week references can be made beyond the symmetric-vs-public-key contrast it explicitly draws.

---
*Sources: CSIT314 Week 9 lecture slides (Public-Key Cryptography). Version: 1.*
