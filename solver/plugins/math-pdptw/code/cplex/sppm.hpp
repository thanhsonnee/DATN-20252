#ifndef __H_SPPM_H__
#define __H_SPPM_H__

#include "../common/data.hpp"
#include "../common/defs.hpp"
#include "../common/route.hpp"
#include "../common/solution.hpp"
#include <boost/dynamic_bitset.hpp>
#include <map>

// CPLEX / SPP stub — CPLEX is not available; SPP phase is disabled.
// solve() returns a large value so the caller never records an improvement.

class SPPModel {
public:
    double solve(const Data& data,
                 std::map<boost::dynamic_bitset<>, Route>& route_pool,
                 Solution& s,
                 Solution& sbest);
};

#endif //__H_SPPM_H__
