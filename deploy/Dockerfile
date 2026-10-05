# The `deployer` image: what `python scripts/stack.py deploy` needs, so that Docker Compose can run it.
#
# It carries only dependencies, never the project's own files. At run time Compose mounts the repository
# at /work (so deployed-addresses.json and paladin-runtime/ land on the host, where `stack.py` and the
# tests expect them) and runs the code from there. Anything baked in under /work would be hidden by
# that mount, so the contract packages live in /opt and CONTRACTS_NODE_MODULES points at them.
#
# Local demo only: the job also gets the Docker socket, so it can restart the Paladin nodes.

# 1. The pinned T-REX and OnchainID contract artifacts (the same `npm ci` as `cd contracts && npm ci`).
FROM node:24-slim AS contracts
WORKDIR /contracts
COPY contracts/package.json contracts/package-lock.json ./
RUN npm ci --no-audit --no-fund

# 2. Python, the project's dependencies, and the Docker client (only the client).
FROM python:3.13-slim
COPY --from=docker:29-cli /usr/local/bin/docker /usr/local/bin/docker
WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
# Installs the dependencies from pyproject.toml. The copy of `src` this puts in site-packages is
# shadowed at run time by the mounted repository (scripts/stack.py puts the repository first).
RUN pip install --no-cache-dir .
COPY --from=contracts /contracts/node_modules /opt/contracts/node_modules
ENV CONTRACTS_NODE_MODULES=/opt/contracts/node_modules
WORKDIR /work
