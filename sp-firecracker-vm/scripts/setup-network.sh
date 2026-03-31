#!/bin/bash
# Set up TAP networking for Firecracker VMs
#
# Creates a TAP device and configures iptables so the VM can ONLY
# reach the SignalPilot gateway. All other outbound traffic is denied.
#
# Usage: ./setup-network.sh <vm_id> <gateway_ip> <gateway_port>

set -euo pipefail

VM_ID="${1:?Usage: setup-network.sh <vm_id> <gateway_ip> <gateway_port>}"
GATEWAY_IP="${2:-172.17.0.1}"
GATEWAY_PORT="${3:-3100}"

TAP_DEV="tap_${VM_ID}"
TAP_IP="172.16.${RANDOM:0:1}.1"
VM_IP="172.16.${RANDOM:0:1}.2"
MASK="255.255.255.252"  # /30 — only two usable IPs

echo "Setting up network for VM ${VM_ID}..."

# Create TAP device
ip tuntap add dev "${TAP_DEV}" mode tap
ip addr add "${TAP_IP}/30" dev "${TAP_DEV}"
ip link set "${TAP_DEV}" up

# Enable IP forwarding
echo 1 > /proc/sys/net/ipv4/ip_forward

# Allow VM → gateway ONLY
iptables -A FORWARD -i "${TAP_DEV}" -d "${GATEWAY_IP}" -p tcp --dport "${GATEWAY_PORT}" -j ACCEPT
iptables -A FORWARD -i "${TAP_DEV}" -j DROP  # Block everything else

# NAT for the gateway traffic
iptables -t nat -A POSTROUTING -s "${VM_IP}/30" -d "${GATEWAY_IP}" -j MASQUERADE

echo "Network ready:"
echo "  TAP device: ${TAP_DEV}"
echo "  VM IP:      ${VM_IP}"
echo "  Gateway:    ${GATEWAY_IP}:${GATEWAY_PORT} (ONLY allowed destination)"

# Output config for Firecracker API
cat << EOF
{
    "iface_id": "eth0",
    "guest_mac": "AA:FC:00:00:00:01",
    "host_dev_name": "${TAP_DEV}",
    "guest_addr": "${VM_IP}",
    "gateway_addr": "${TAP_IP}",
    "mask": "${MASK}"
}
EOF
