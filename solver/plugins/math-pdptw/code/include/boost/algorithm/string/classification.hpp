#pragma once
#include <string>

// Minimal stub for boost::algorithm::string::is_any_of

namespace boost {

struct is_any_of_pred {
    std::string chars;
    explicit is_any_of_pred(const std::string& c) : chars(c) {}
    bool operator()(char c) const { return chars.find(c) != std::string::npos; }
};

inline is_any_of_pred is_any_of(const std::string& chars) {
    return is_any_of_pred(chars);
}

} // namespace boost
