import { defineConfig } from "hardhat/config";

// evmVersion shanghai is what the chain, FireFly and Paladin need (plan D-08).
export default defineConfig({
  solidity: {
    version: "0.8.28",
    settings: {
      evmVersion: "shanghai",
      optimizer: { enabled: true, runs: 200 },
    },
  },
  paths: {
    sources: "./contracts",
    tests: { solidity: "./test" },
  },
});
