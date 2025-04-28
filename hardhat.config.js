// hardhat.config.js
require("@nomiclabs/hardhat-ethers");

module.exports = {
    solidity: "0.8.19",
    networks: {
        hardhat: {
            chainId: process.env.CHAIN_ID,
            forking: {
                url: process.env.ETHEREUM_RPC_URL,
                blockNumber: undefined,
            },
        },
  },
};