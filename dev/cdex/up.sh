#!/usr/bin/env bash
#
# Build and run the CDEX-over-SPICE container.
#
# Usage: ./up.sh [OPTIONS]
#
# After it finishes, connect from the host with a SPICE client:
#   remote-viewer spice://localhost:5900
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

# Defaults from environment variables.
X11SPICE_IMAGE="${X11SPICE_IMAGE:-cusdeb-os:x11spice}"
IMAGE="${IMAGE:-cusdeb-os:cdex}"
CONTAINER="${CONTAINER:-cdex}"
SPICE_PORT="${SPICE_PORT:-5900}"
SPICE_BIND="${SPICE_BIND:-127.0.0.1}"
export SPICE_PASSWORD="${SPICE_PASSWORD:-secret}"
RESOLUTION="${RESOLUTION:-1280x720x24}"

# Runtime options.
REBUILD=false
FORCE_REBUILD_CDEX=false
FORCE_REBUILD_FULL=false

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Build and run the CDEX-over-SPICE container.

Options:
  -h, --help                  Show this help message and exit
  -r, --rebuild               Force rebuild both images with cache
  -c, --force-rebuild-cdex    Force rebuild cdex runtime without cache
  -f, --force-rebuild-full    Force rebuild base + cdex runtime without cache
  -p, --port PORT             SPICE port (default: ${SPICE_PORT})
  -b, --bind IP               SPICE bind address (default: ${SPICE_BIND})
  -C, --container NAME        Container name (default: ${CONTAINER})
      --resolution WxHxD      Display resolution (default: ${RESOLUTION})

Environment variables (override defaults):
  X11SPICE_IMAGE, IMAGE, CONTAINER, SPICE_PORT, SPICE_BIND,
  SPICE_PASSWORD, RESOLUTION

Examples:
  $0                          Build (if needed) and start
  $0 --rebuild                Force rebuild both images with cache
EOF
}

log() {
    local level="$1"
    shift
    echo "[${level}] $*" >&2
}

validate_config() {
    if ! command -v docker >/dev/null 2>&1; then
        log error "docker is not installed or not in PATH"
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        log error "docker daemon is not running"
        exit 1
    fi

    if ! [[ "${SPICE_PORT}" =~ ^[0-9]+$ ]] || [ "${SPICE_PORT}" -lt 1 ] || [ "${SPICE_PORT}" -gt 65535 ]; then
        log error "SPICE_PORT must be an integer between 1 and 65535 (got: ${SPICE_PORT})"
        exit 1
    fi

    if [ -z "${SPICE_BIND}" ]; then
        log error "SPICE_BIND must not be empty"
        exit 1
    fi

    if [[ "${SPICE_BIND}" =~ [^[:alnum:].:] ]]; then
        log error "SPICE_BIND contains invalid characters (got: ${SPICE_BIND})"
        exit 1
    fi

    if ! [[ "${RESOLUTION}" =~ ^[1-9][0-9]*x[1-9][0-9]*x([1-9]|[12][0-9]|3[0-2])$ ]]; then
        log error "RESOLUTION must use positive WxHxD with depth 1-32 (got: ${RESOLUTION})"
        exit 1
    fi

    if [ -z "${X11SPICE_IMAGE}" ] || [ -z "${IMAGE}" ] || [ -z "${CONTAINER}" ]; then
        log error "X11SPICE_IMAGE, IMAGE, and CONTAINER must not be empty"
        exit 1
    fi
}

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            -h|--help)
                usage
                exit 0
                ;;
            -r|--rebuild)
                REBUILD=true
                shift
                ;;
            -c|--force-rebuild-cdex)
                FORCE_REBUILD_CDEX=true
                shift
                ;;
            -f|--force-rebuild-full)
                FORCE_REBUILD_FULL=true
                shift
                ;;
            -p|--port)
                if [ $# -lt 2 ]; then
                    log error "Option $1 requires an argument"
                    exit 1
                fi
                SPICE_PORT="$2"
                shift 2
                ;;
            -b|--bind)
                if [ $# -lt 2 ]; then
                    log error "Option $1 requires an argument"
                    exit 1
                fi
                SPICE_BIND="$2"
                shift 2
                ;;
            -C|--container)
                if [ $# -lt 2 ]; then
                    log error "Option $1 requires an argument"
                    exit 1
                fi
                CONTAINER="$2"
                shift 2
                ;;
            --resolution)
                if [ $# -lt 2 ]; then
                    log error "Option $1 requires an argument"
                    exit 1
                fi
                RESOLUTION="$2"
                shift 2
                ;;
            *)
                log error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
}

build_x11spice() {
    if [ "${FORCE_REBUILD_FULL}" = true ] || [ "${REBUILD}" = true ] || ! docker image inspect "${X11SPICE_IMAGE}" >/dev/null 2>&1; then
        log info "Building ${X11SPICE_IMAGE} ..."
        local args=(--network=host -f Dockerfile.x11spice -t "${X11SPICE_IMAGE}" "${HERE}")
        [ "${FORCE_REBUILD_FULL}" = true ] && args+=(--no-cache)
        docker build "${args[@]}"
    else
        log info "Using existing ${X11SPICE_IMAGE}"
    fi
}

build_cdex() {
    if [ "${FORCE_REBUILD_FULL}" = true ] || [ "${FORCE_REBUILD_CDEX}" = true ] || [ "${REBUILD}" = true ] || ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
        log info "Building ${IMAGE} ..."
        local args=(--network=host -f Dockerfile -t "${IMAGE}" --build-arg X11SPICE_IMAGE="${X11SPICE_IMAGE}" "${HERE}")
        { [ "${FORCE_REBUILD_FULL}" = true ] || [ "${FORCE_REBUILD_CDEX}" = true ]; } && args+=(--no-cache)
        docker build "${args[@]}"
    else
        log info "Using existing ${IMAGE}"
    fi
}

run_container() {
    log info "Starting container ${CONTAINER} ..."
    docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
    docker run -d --name "${CONTAINER}" \
        -p "${SPICE_BIND}:${SPICE_PORT}:5900" \
        -e SPICE_PASSWORD \
        -e RESOLUTION="${RESOLUTION}" \
        "${IMAGE}"

    log info "Up. CDEX takes ~20-40s to finish loading."
    log info "Connect from the host with a SPICE client:"
    log info "    remote-viewer spice://${SPICE_BIND}:${SPICE_PORT}"
    log info "Stop: docker rm -f ${CONTAINER}"
}

main() {
    parse_args "$@"
    validate_config

    export DOCKER_BUILDKIT=1

    build_x11spice
    build_cdex
    run_container
}

main "$@"
