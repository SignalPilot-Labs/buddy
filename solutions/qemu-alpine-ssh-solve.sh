#!/bin/bash
set -e

apt-get update && apt-get install -y qemu-system-x86 expect sshpass 2>/dev/null || true

# Boot Alpine ISO with port forwarding (host 2222 -> guest 22)
qemu-system-x86_64 \
    -m 512 \
    -cdrom /app/alpine.iso \
    -boot d \
    -nographic \
    -serial mon:stdio \
    -display none \
    -net nic \
    -net user,hostfwd=tcp::2222-:22 \
    -no-reboot &

QEMU_PID=$!
echo "QEMU PID: $QEMU_PID"

# Wait for boot
echo "Waiting for Alpine to boot..."
sleep 45

# Use expect to configure the VM via serial console
# Login as root (no password), set password, install SSH, start sshd
expect << 'EXPECT_EOF'
set timeout 60
spawn telnet 127.0.0.1 6665
expect {
    "localhost login:" { send "root\r" }
    timeout { send "\r" }
}
expect "# "
send "echo root:password123 | chpasswd\r"
expect "# "
send "apk add openssh\r"
expect "# "
send "ssh-keygen -A\r"
expect "# "
send "echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config\r"
expect "# "
send "/usr/sbin/sshd\r"
expect "# "
send "exit\r"
EXPECT_EOF

# Actually, with -nographic and no separate console, we need a different approach
# Let's use the serial console directly
sleep 5

# Use socat or direct approach with the serial console
# Since we started with -nographic, the serial console is on stdio
# We can pipe commands through it

# Better approach: use -monitor telnet and serial as stdin/stdout
# Kill and restart with proper config
kill $QEMU_PID 2>/dev/null || true
sleep 2

# Restart with serial on a telnet port and monitor on another
qemu-system-x86_64 \
    -m 512 \
    -cdrom /app/alpine.iso \
    -boot d \
    -nographic \
    -serial telnet:127.0.0.1:4321,server,nowait \
    -display none \
    -net nic \
    -net user,hostfwd=tcp::2222-:22 \
    -no-reboot &

echo "Waiting for boot (attempt 2)..."
sleep 45

# Configure via expect over telnet
expect << 'EXPECT_EOF'
set timeout 120
spawn telnet 127.0.0.1 4321

# Wait for login prompt
expect {
    "localhost login:" { }
    timeout { send "\r"; expect "localhost login:" }
}

send "root\r"
expect "# "

# Set root password
send "echo 'root:password123' | chpasswd\r"
expect "# "

# Setup networking
send "setup-interfaces -a\r"
expect {
    "# " { }
    "Available" { send "\r"; expect "# " }
}

# Install openssh
send "apk update\r"
expect "# "
send "apk add openssh\r"
expect "# "

# Generate host keys
send "ssh-keygen -A\r"
expect "# "

# Allow root login
send "sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config\r"
expect "# "
send "echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config\r"
expect "# "

# Start sshd
send "/usr/sbin/sshd\r"
expect "# "

send "echo SSH SETUP COMPLETE\r"
expect "SSH SETUP COMPLETE"
EXPECT_EOF

echo "Verifying SSH..."
sleep 5
sshpass -p password123 ssh -o StrictHostKeyChecking=no -p 2222 root@localhost uname -r || echo "SSH not ready yet, waiting..."
sleep 10
sshpass -p password123 ssh -o StrictHostKeyChecking=no -p 2222 root@localhost uname -r
echo "Done!"
