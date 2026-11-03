FROM node:20-alpine AS builder

# QUEDERA Pulse (cmmi-app-v4) frontend — Next.js 14 + next start (production).
# BACKEND_URL is set at build time via NEXT_PUBLIC_API_URL. Same shape as
# cmmi-app/frontend/Dockerfile; the rebranded Pulse source lives in src/.

WORKDIR /app

# Install dependencies (cache layer)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy frontend code
COPY frontend/ ./

# Copy branding kit into the container so tailwind.config.js can
# `require("../../branding/quedera-tailwind-preset.cjs")` and globals.css can
# `@import "../../../../branding/quedera-tokens.css"` at build time.
# Both paths resolve to /branding/ from inside the image (WORKDIR is /app,
# so ../../ from /app goes to /, then /branding/...). Sibling of /app.
COPY branding/ /branding/

# Build-time backend URL — baked into the static bundle via Next.js inlining.
# For Azure: pass --build-arg NEXT_PUBLIC_API_URL=https://<backend-fqdn>
# For local docker-compose: defaults to http://localhost:8000
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Verify the env var is actually set before next build reads it
RUN echo ">>> Building with NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}"

# Cap the Node heap. This host has ~8G available and the Next.js build was
# being OOM-killed at the default heap size (swap exhausted mid-build, no
# error in the log). 2G is plenty for this app and leaves room for the
# rest of the box.
ENV NODE_OPTIONS=--max-old-space-size=2048
RUN npm run build

# --- runtime stage ---
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000

# Re-declare the ARG in the runtime stage: build args do NOT cross stage
# boundaries. Without this the runtime env is empty and next.config.js falls
# back to http://localhost:8003, so /api/* rewrites die on Azure.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Copy only what we need to run
COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

EXPOSE 3000

# Health check (Azure container probes)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["npm", "start"]