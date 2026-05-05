#pragma once
#include <vector>
#include <cstddef>

// Minimal boost::dynamic_bitset<> compatibility stub (no Boost required).
// Implements all operations used in the math-pdptw codebase.

namespace boost {

template<typename Block = unsigned long>
class dynamic_bitset {
    static const size_t BPB = sizeof(Block) * 8; // bits per block
    static size_t nblk(size_t n) { return (n + BPB - 1) / BPB; }

public:
    // ── Proxy reference for non-const operator[] ─────────────────────────────
    struct reference {
        dynamic_bitset& bs;
        size_t pos;
        reference(dynamic_bitset& b, size_t p) : bs(b), pos(p) {}

        reference& operator=(bool val) {
            size_t blk = pos / BPB, bit = pos % BPB;
            if (val) bs.blocks[blk] |=  (Block(1) << bit);
            else     bs.blocks[blk] &= ~(Block(1) << bit);
            return *this;
        }
        // Support chained assignment: a[i] = a[j] = true
        reference& operator=(const reference& rhs) { return *this = (bool)rhs; }

        operator bool() const {
            return (bs.blocks[pos / BPB] >> (pos % BPB)) & Block(1);
        }
    };

    // ── Constructors ──────────────────────────────────────────────────────────
    dynamic_bitset() : nbits(0) {}
    explicit dynamic_bitset(size_t n, Block val = Block(0))
        : nbits(n), blocks(nblk(n), Block(0)) {
        if (n > 0 && val != 0) blocks[0] = val;
    }

    // ── Element access ────────────────────────────────────────────────────────
    bool operator[](size_t pos) const {
        return (blocks[pos / BPB] >> (pos % BPB)) & Block(1);
    }
    reference operator[](size_t pos) { return reference(*this, pos); }

    // ── Whole-bitset queries ──────────────────────────────────────────────────
    size_t size() const { return nbits; }

    bool all() const {
        if (nbits == 0) return true;
        size_t full = nbits / BPB;
        for (size_t i = 0; i < full; i++)
            if (blocks[i] != ~Block(0)) return false;
        size_t rem = nbits % BPB;
        if (rem > 0) {
            Block mask = (Block(1) << rem) - 1;
            if ((blocks[full] & mask) != mask) return false;
        }
        return true;
    }

    bool none() const {
        for (auto b : blocks) if (b != Block(0)) return false;
        return true;
    }

    bool any() const { return !none(); }

    size_t count() const {
        size_t cnt = 0;
        for (auto b : blocks) {
            Block tmp = b;
            while (tmp) { cnt += tmp & 1; tmp >>= 1; }
        }
        return cnt;
    }

    // ── Modifier operations ───────────────────────────────────────────────────
    dynamic_bitset& set() {
        for (auto& b : blocks) b = ~Block(0);
        return *this;
    }

    dynamic_bitset& reset() {
        for (auto& b : blocks) b = Block(0);
        return *this;
    }

    // ── Bitwise operators ─────────────────────────────────────────────────────
    dynamic_bitset operator|(const dynamic_bitset& o) const {
        dynamic_bitset r(nbits);
        for (size_t i = 0; i < blocks.size(); i++) r.blocks[i] = blocks[i] | o.blocks[i];
        return r;
    }
    dynamic_bitset& operator|=(const dynamic_bitset& o) {
        for (size_t i = 0; i < blocks.size(); i++) blocks[i] |= o.blocks[i];
        return *this;
    }

    dynamic_bitset operator^(const dynamic_bitset& o) const {
        dynamic_bitset r(nbits);
        for (size_t i = 0; i < blocks.size(); i++) r.blocks[i] = blocks[i] ^ o.blocks[i];
        return r;
    }
    dynamic_bitset& operator^=(const dynamic_bitset& o) {
        for (size_t i = 0; i < blocks.size(); i++) blocks[i] ^= o.blocks[i];
        return *this;
    }

    dynamic_bitset operator&(const dynamic_bitset& o) const {
        dynamic_bitset r(nbits);
        for (size_t i = 0; i < blocks.size(); i++) r.blocks[i] = blocks[i] & o.blocks[i];
        return r;
    }
    dynamic_bitset& operator&=(const dynamic_bitset& o) {
        for (size_t i = 0; i < blocks.size(); i++) blocks[i] &= o.blocks[i];
        return *this;
    }

    // ── Comparison (required for use as std::map key) ─────────────────────────
    bool operator<(const dynamic_bitset& o) const {
        if (nbits != o.nbits) return nbits < o.nbits;
        for (int i = (int)blocks.size() - 1; i >= 0; i--)
            if (blocks[i] != o.blocks[i]) return blocks[i] < o.blocks[i];
        return false;
    }
    bool operator==(const dynamic_bitset& o) const {
        return nbits == o.nbits && blocks == o.blocks;
    }

private:
    size_t nbits;
    std::vector<Block> blocks;
};

} // namespace boost
