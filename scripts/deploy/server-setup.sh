#!/usr/bin/env bash
# One-time preparation of a fresh Ubuntu 22.04/24.04 server (x86_64 or ARM64, e.g. Oracle Cloud
# Ampere A1) for API Sentinel. Run as the default sudo user (e.g. "ubuntu"):
#
#   bash scripts/deploy/server-setup.sh
#
# It installs Docker Engine + Compose plugin from Docker's official apt repository, opens TCP 80,
# TCP/UDP 443 in the host firewall (Oracle's Ubuntu images reject everything except SSH by
# default), persists those rules, and adds the current user to the docker group.
# It never opens PostgreSQL (5432), the analyzer (8081) or the backend (8080).
set -euo pipefail

if [[ $EUID -eq 0 ]]; then
  echo "Run this as your normal sudo user, not root." >&2
  exit 1
fi

. /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "This script supports Ubuntu only (found: ${ID:-unknown})." >&2
  exit 1
fi

echo "== Installing Docker Engine from download.docker.com"
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl git iptables-persistent python3
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker

echo "== Opening TCP 80, TCP 443 and UDP 443 in the host firewall"
open_port() {
  local proto=$1 port=$2
  if ! sudo iptables -C INPUT -p "$proto" -m state --state NEW -m "$proto" --dport "$port" -j ACCEPT 2>/dev/null; then
    # Insert near the top so it comes before Oracle's final REJECT rule.
    sudo iptables -I INPUT 5 -p "$proto" -m state --state NEW -m "$proto" --dport "$port" -j ACCEPT
  fi
}
open_port tcp 80
open_port tcp 443
open_port udp 443
sudo netfilter-persistent save

echo "== Adding $USER to the docker group"
sudo usermod -aG docker "$USER"

docker_version=$(sudo docker version --format '{{.Server.Version}}')
compose_version=$(sudo docker compose version --short)
echo
echo "Docker ${docker_version}, Compose ${compose_version} installed."
echo "Log out and back in (so the docker group applies), then run scripts/deploy/deploy.sh."
