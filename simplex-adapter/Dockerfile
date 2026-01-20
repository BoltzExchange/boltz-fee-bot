# Build stage - use Debian for glibc compatibility with native modules
FROM node:20-bookworm AS builder

WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies (native modules will build here)
RUN npm install

# Copy source
COPY tsconfig.json ./
COPY src ./src

# Build TypeScript
RUN npm run build

# Prune dev dependencies
RUN npm prune --production

# Production stage - also Debian for glibc
FROM node:20-bookworm-slim

# Install runtime dependencies for native modules and healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the already-built node_modules (with native binaries) from builder
COPY --from=builder /app/node_modules ./node_modules

# Copy package.json for reference
COPY package.json ./

# Copy built files
COPY --from=builder /app/dist ./dist

# Copy bot avatar
COPY bot-avatar.png ./

# Create data directory for bot profile persistence
RUN mkdir -p /app/data

# Expose bridge port
EXPOSE 3000

# Run the bridge
CMD ["node", "dist/index.js"]
