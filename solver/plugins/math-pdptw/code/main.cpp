#include "common/defs.hpp"
#include "common/data.hpp"
#include "common/resultinfo.hpp"
#include "common/parameters.hpp"
#include "lns/lns.hpp"
#include <iostream>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <sstream>
#include "algo/algorithm.hpp"
#include <getopt.h>

using namespace std;

Parameters read_parameters(int argc, char** argv);

int main(int argc, char** argv){
    Parameters par = read_parameters(argc, argv);

    Data data;
    if (par.inst_path == "") {
        printf("Reading instance from stdin.\n");
        if (data.read_from_stdin(par.inst_format) == Data::READ_FAIL) {
            printf("Failed reading from stdin.\n");
            return EXIT_FAILURE;
        }
    } else {
        printf("Reading instance from file '%s'.\n", par.inst_path.c_str());
        if (data.read_from_file(par.inst_path.c_str(), par.inst_format) == Data::READ_FAIL) {
            printf("Failed reading from the file '%s'.\n", par.inst_path.c_str());
            return EXIT_FAILURE;
        }
    }
    cout.precision(16);

    printd(("Pre-processing.\n"));
    Data::pre_process(data);
    Data::compute_conflicts(data);
    printd(("Pre-processing: %i tightenings | %i conflicts\n", data.nref, data.nconf));

    ResultInfo rinfo;
    Algorithm alg(data, par);
    rinfo = alg.solve();

    if(par.print_type == Def::PRINT_TABLE_FORMAT){
        rinfo.print_table_format(data);
    }else if(par.print_type == Def::PRINT_IRACE_FORMAT){
        rinfo.print_irace_format(data);
    }else{
        rinfo.print_human_format(data);
    }

    if(par.write_solution){
        if(Data::write_solution(data, rinfo.sb, par.solution_file) == Data::WRITE_FAIL)
            printf("Failed writing solution to file %s\n", par.solution_file.c_str());
    }

    return 0;
}

static void print_usage(const char* prog) {
    printf("Usage: %s [options]\n", prog);
    printf("  -h, --help                    print help\n");
    printf("  -i, --instance <path>         instance file path (default: stdin)\n");
    printf("  -f, --format <fmt>            instance format: ll, bcp, umovme, sb (default: ll)\n");
    printf("  -s, --seed <n>                RNG seed (default: 0)\n");
    printf("  -t, --time <sec>              time limit in seconds (default: 60)\n");
    printf("      --print <fmt>             output format: human, table, irace (default: human)\n");
    printf("      --alg-use-spp <bool>      use SPP phase: true/false (default: false)\n");
    printf("      --alg-pert-prob <d>       perturbation probability (default: 0.57)\n");
    printf("      --alg-ages <type>         AGES type: original/new (default: new)\n");
    printf("      --alg-perc-pert-size <d>  perturbation percentage (default: 0.83)\n");
    printf("      --ages-max-iter <n>       AGES max iterations (default: 4000)\n");
    printf("      --ages-pert-size <n>      AGES perturbation size (default: 100)\n");
    printf("      --ages-perc-pert-size <d> AGES perturbation pct (default: 0.15)\n");
    printf("      --lns-min-q <n>           LNS min removal (default: 2)\n");
    printf("      --lns-max-perc-q <d>      LNS max removal pct (default: 0.20)\n");
    printf("      --lns-min-k <n>           LNS min routes for regret (default: 1)\n");
    printf("      --lns-max-k <n>           LNS max routes for regret (default: 4)\n");
    printf("      --lns-max-iter <n>        LNS max iterations (default: 970)\n");
    printf("      --lns-lsize <n>           LNS LAHC list size (default: 1540)\n");
    printf("      --lns-rollback <bool>     LNS rollback to best (default: true)\n");
    printf("      --lns-weight-shaw <n>     weight for shaw removal (default: 6)\n");
    printf("      --lns-weight-random <n>   weight for random removal (default: 3)\n");
    printf("      --log-file <path>         log file path\n");
    printf("      --solution <path>         write solution to file\n");
}

static bool parse_bool(const char* s) {
    return (strcmp(s, "true") == 0 || strcmp(s, "1") == 0 || strcmp(s, "yes") == 0);
}

Parameters read_parameters(int argc, char** argv){
    Parameters par;
    // SPP is stubbed, disable by default so route pool overhead is skipped
    par.use_spp = false;

    enum LongOpts {
        OPT_PRINT = 256, OPT_USE_SPP, OPT_PERT_PROB, OPT_AGES, OPT_PERC_PERT,
        OPT_AGES_MAX_ITER, OPT_AGES_PERT_SIZE, OPT_AGES_PERC_PERT,
        OPT_LNS_MIN_Q, OPT_LNS_MAX_PERC_Q, OPT_LNS_MIN_K, OPT_LNS_MAX_K,
        OPT_LNS_MAX_ITER, OPT_LNS_LSIZE, OPT_LNS_ROLLBACK,
        OPT_LNS_W_SHAW, OPT_LNS_W_RANDOM,
        OPT_LOG_FILE, OPT_SOLUTION
    };

    static struct option long_options[] = {
        {"help",               no_argument,       0, 'h'},
        {"instance",           required_argument, 0, 'i'},
        {"format",             required_argument, 0, 'f'},
        {"seed",               required_argument, 0, 's'},
        {"time",               required_argument, 0, 't'},
        {"print",              required_argument, 0, OPT_PRINT},
        {"alg-use-spp",        required_argument, 0, OPT_USE_SPP},
        {"alg-pert-prob",      required_argument, 0, OPT_PERT_PROB},
        {"alg-ages",           required_argument, 0, OPT_AGES},
        {"alg-perc-pert-size", required_argument, 0, OPT_PERC_PERT},
        {"ages-max-iter",      required_argument, 0, OPT_AGES_MAX_ITER},
        {"ages-pert-size",     required_argument, 0, OPT_AGES_PERT_SIZE},
        {"ages-perc-pert-size",required_argument, 0, OPT_AGES_PERC_PERT},
        {"lns-min-q",          required_argument, 0, OPT_LNS_MIN_Q},
        {"lns-max-perc-q",     required_argument, 0, OPT_LNS_MAX_PERC_Q},
        {"lns-min-k",          required_argument, 0, OPT_LNS_MIN_K},
        {"lns-max-k",          required_argument, 0, OPT_LNS_MAX_K},
        {"lns-max-iter",       required_argument, 0, OPT_LNS_MAX_ITER},
        {"lns-lsize",          required_argument, 0, OPT_LNS_LSIZE},
        {"lns-rollback",       required_argument, 0, OPT_LNS_ROLLBACK},
        {"lns-weight-shaw",    required_argument, 0, OPT_LNS_W_SHAW},
        {"lns-weight-random",  required_argument, 0, OPT_LNS_W_RANDOM},
        {"log-file",           required_argument, 0, OPT_LOG_FILE},
        {"solution",           required_argument, 0, OPT_SOLUTION},
        {0, 0, 0, 0}
    };

    int c, opt_idx = 0;
    bool ages_type_explicit = false;
    string str_alg_ages = Def::AGES_NEW;

    while ((c = getopt_long(argc, argv, "hi:f:s:t:", long_options, &opt_idx)) != -1) {
        switch(c) {
        case 'h': print_usage(argv[0]); exit(EXIT_SUCCESS);
        case 'i': par.inst_path = optarg; break;
        case 'f': par.inst_format = optarg; break;
        case 's': par.seed = (mt19937_64::result_type)atol(optarg); break;
        case 't': par.max_time = atof(optarg); break;
        case OPT_PRINT:          par.print_type = optarg; break;
        case OPT_USE_SPP:        par.use_spp = parse_bool(optarg); break;
        case OPT_PERT_PROB:      par.prob_eval = atof(optarg); break;
        case OPT_AGES:           str_alg_ages = optarg; ages_type_explicit = true; break;
        case OPT_PERC_PERT:      par.ppsize = atof(optarg); break;
        case OPT_AGES_MAX_ITER:  par.ges_max_iter = (size_t)atol(optarg); break;
        case OPT_AGES_PERT_SIZE: par.ges_psize = (size_t)atol(optarg); break;
        case OPT_AGES_PERC_PERT: par.ges_ppsize = atof(optarg); break;
        case OPT_LNS_MIN_Q:      par.lns_min_q = atoi(optarg); break;
        case OPT_LNS_MAX_PERC_Q: par.lns_max_mult = atof(optarg); break;
        case OPT_LNS_MIN_K:      par.lns_min_k = atoi(optarg); break;
        case OPT_LNS_MAX_K:      par.lns_max_k = atoi(optarg); break;
        case OPT_LNS_MAX_ITER:   par.lns_max_iter = atoi(optarg); break;
        case OPT_LNS_LSIZE:      par.lns_lsize = atoi(optarg); break;
        case OPT_LNS_ROLLBACK:   par.lns_rollback = parse_bool(optarg); break;
        case OPT_LNS_W_SHAW:     par.lns_wrem[LNS::REM_SHAW_TYPE] = atoi(optarg); break;
        case OPT_LNS_W_RANDOM:   par.lns_wrem[LNS::REM_RANDOM_TYPE] = atoi(optarg); break;
        case OPT_LOG_FILE:       par.log_filename = optarg; break;
        case OPT_SOLUTION:       par.solution_file = optarg; break;
        default: break;
        }
    }

    if (str_alg_ages == Def::AGES_ORIGINAL)
        par.alg_ages = Def::AGES_ORIGINAL_TYPE;
    else
        par.alg_ages = Def::AGES_NEW_TYPE;

    par.lns_wrem[LNS::REM_WORST_TYPE] = 10 - par.lns_wrem[LNS::REM_SHAW_TYPE] - par.lns_wrem[LNS::REM_RANDOM_TYPE];

    if(par.solution_file.size() > 0) par.write_solution = true;
    if(par.log_filename.size() > 0)  par.save_log = true;

    return par;
}
