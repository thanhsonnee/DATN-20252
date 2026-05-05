#include "sppm.hpp"

// CPLEX stub — SPP phase disabled; AGES + LNS heuristic still runs normally.
double SPPModel::solve(const Data& /*data*/,
                       std::map<boost::dynamic_bitset<>, Route>& /*route_pool*/,
                       Solution& /*s*/,
                       Solution& /*sbest*/) {
    return 1e18; // never triggers an "improvement" in the caller
}
