#pragma once
#include <string>
#include <vector>
#include "classification.hpp"

// Minimal stub for boost::algorithm::string::split + token_compress_on/off

namespace boost {

enum token_compress_mode_type { token_compress_off = 0, token_compress_on = 1 };

template<typename Sequence, typename Predicate>
void split(Sequence& result, const std::string& input, Predicate pred,
           token_compress_mode_type compress = token_compress_off) {
    result.clear();
    std::string tok;
    for (char c : input) {
        if (pred(c)) {
            if (!tok.empty() || compress == token_compress_off) {
                result.push_back(tok);
                tok.clear();
            }
        } else {
            tok += c;
        }
    }
    if (!tok.empty() || compress == token_compress_off)
        result.push_back(tok);
}

} // namespace boost
