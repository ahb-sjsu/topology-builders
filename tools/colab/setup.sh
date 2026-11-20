#!/bin/bash
# Set up a Colab runtime, or any Ubuntu 24.04 machine where you are root, to run the labs without Docker: FRR from
# FRR pull request 24128 (flood reduction, draft-ietf-lsr-distoptflood; riw777/frr at e263c441), built with only the
# daemons the labs use (mgmtd, zebra, staticd, isisd), and topology-builders. Run it once per runtime; a second run
# skips what is already installed.
#
#   bash tools/colab/setup.sh
#
# Environment: FRR_REF (commit), FRR_URL (source tarball), TB_PACKAGE (what pip installs; default: this checkout).
set -euo pipefail
FRR_REF="${FRR_REF:-e263c441160c7cf25749a9695978ffe5649678f9}"
FRR_URL="${FRR_URL:-https://github.com/riw777/frr/archive/$FRR_REF.tar.gz}"
# FRR needs libyang 2.1.128 or later; Ubuntu 24.04's is older, so it is built from source as FRR's
# doc/developer/building-libyang.rst does.
LIBYANG_REF="${LIBYANG_REF:-v2.1.128}"
LOG=/opt/frr-build.log
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TB_PACKAGE="${TB_PACKAGE:-$(cd "$HERE/../.." && pwd)}"
t0=$(date +%s)

[ "$(id -u)" = 0 ] || { echo "setup.sh: run as root (Colab cells are root)"; exit 1; }
. /etc/os-release
[ "${VERSION_ID:-}" = 24.04 ] || echo "setup.sh: tested on Ubuntu 24.04; this is ${PRETTY_NAME:-unknown}, continuing"

step() {  # run a build step into the log; on failure show its end and stop
  "$@" >> "$LOG" 2>&1 || { echo "setup.sh: failed: $*"; tail -40 "$LOG"; exit 1; }
}

echo "== packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  ca-certificates curl iproute2 util-linux python3 python3-pip python3-dev git autoconf automake libtool make \
  cmake pkg-config bison flex perl build-essential libreadline-dev libpam0g-dev libjson-c-dev libc-ares-dev \
  libcap-dev libelf-dev libunwind-dev libpcre2-dev protobuf-c-compiler libprotobuf-c-dev > /dev/null
: > "$LOG"

if pkg-config --atleast-version=2.1.128 libyang 2>/dev/null; then
  echo "== libyang $(pkg-config --modversion libyang) already installed"
else
  echo "== libyang $LIBYANG_REF: download and build"
  rm -rf /opt/libyang-src && mkdir -p /opt/libyang-src
  curl -fsSL "https://github.com/CESNET/libyang/archive/refs/tags/$LIBYANG_REF.tar.gz" \
    | tar -xz -C /opt/libyang-src --strip-components=1
  step cmake -S /opt/libyang-src -B /opt/libyang-src/build -D CMAKE_INSTALL_PREFIX:PATH=/usr \
    -D CMAKE_BUILD_TYPE:String=Release -D ENABLE_TESTS=OFF
  step make -C /opt/libyang-src/build -j"$(nproc)"
  step make -C /opt/libyang-src/build install
  ldconfig
fi

if /usr/lib/frr/isisd --version 2>/dev/null | grep -q "pr24128-${FRR_REF:0:8}"; then
  echo "== FRR ${FRR_REF:0:8} already installed"
else
  echo "== FRR ${FRR_REF:0:8}: download and build (several minutes; about 10 on 2 CPUs is a guess, not a measurement)"
  rm -rf /opt/frr-src && mkdir -p /opt/frr-src
  curl -fsSL "$FRR_URL" | tar -xz -C /opt/frr-src --strip-components=1
  cd /opt/frr-src
  step ./bootstrap.sh
  step ./configure --prefix=/usr --sbindir=/usr/lib/frr --libdir=/usr/lib/frr --libexecdir=/usr/lib/frr \
    --sysconfdir=/etc --localstatedir=/var --with-moduledir=/usr/lib/frr/modules \
    --enable-user=frr --enable-group=frr --enable-multipath=64 \
    --disable-doc --disable-snmp --disable-scripting --disable-bgpd --disable-ripd --disable-ripngd \
    --disable-ospfd --disable-ospf6d --disable-ldpd --disable-nhrpd --disable-eigrpd --disable-babeld \
    --disable-pimd --disable-pim6d --disable-pbrd --disable-sharpd --disable-fabricd --disable-vrrpd \
    --disable-bfdd --disable-pathd --with-pkg-extra-version="-pr24128-${FRR_REF:0:8}"
  step make -j"$(nproc)"
  step make install
  echo /usr/lib/frr > /etc/ld.so.conf.d/frr.conf
  ldconfig
  cd /
fi
getent group frr > /dev/null || groupadd -r frr
getent group frrvty > /dev/null || groupadd -r frrvty
id frr > /dev/null 2>&1 || useradd -r -g frr -G frrvty -d /var/run/frr -s /usr/sbin/nologin frr
for d in mgmtd zebra staticd isisd; do [ -x "/usr/lib/frr/$d" ] || { echo "missing /usr/lib/frr/$d"; exit 1; }; done
/usr/lib/frr/isisd --version | head -1

echo "== topology-builders from $TB_PACKAGE"
python3 -m pip install -q "$TB_PACKAGE" 2>/dev/null \
  || python3 -m pip install -q --break-system-packages "$TB_PACKAGE"
python3 -c "import topology_builders as t; print('topology-builders', t.__version__)"
echo "== done in $(( $(date +%s) - t0 )) s"
