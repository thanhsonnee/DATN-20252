package com.zll.Main;

import java.io.File;
import java.io.IOException;

/**
 * CLI entrypoint for 2E-VRPTWSPD Tabu Search.
 * Usage: java -cp out com.zll.Main.Runner <instanceName> [seed] [timeLimitSec]
 * instanceName: e.g. "100-10-1"  (reads from ./input/Set2/<name>/Set5_<name>.dat)
 */
public class Runner {
    public static void main(String[] args) throws IOException {
        if (args.length < 1) {
            System.err.println("Usage: Runner <instanceName> [seed] [timeLimitSec]");
            System.err.println("  instanceName: e.g. 100-10-1");
            System.exit(1);
        }
        String instanceName = args[0];
        int seed = args.length > 1 ? Integer.parseInt(args[1]) : 0;
        long timeLimitMs = args.length > 2 ? Long.parseLong(args[2]) * 1000L : 0L;

        // Ensure output directory exists (printSolution writes there)
        new File("./output/heuristic/" + instanceName).mkdirs();

        Main.test(instanceName, seed, 0.5, timeLimitMs);
    }
}
