# VM setup for the mDNS mirror

This guide sets up an Ubuntu VM to run the mDNS mirror container. The VM keeps one IP address for management, and each mirrored network gets its own macvlan interface inside the container.

The examples use these names and VLAN IDs. Replace them with your own:

| Network  | VLAN ID | Subnet          | VM address             |
| -------- | ------- | --------------- | ---------------------- |
| personal | 10      | 192.168.10.0/24 | 192.168.10.5 (management) |
| iot      | 20      | 192.168.20.0/24 | none                   |
| nas      | 30      | 192.168.30.0/24 | none                   |

The trunk NIC is `enp3s0`. Find yours with `ip -br link`.

## 1. Configure the trunk NIC and VLANs

Create `/etc/netplan/01-mdns-mirror.yaml`:

```yaml
network:
  version: 2
  ethernets:
    enp3s0:
      dhcp4: false
      dhcp6: false
      link-local: []
  vlans:
    personal:
      id: 10
      link: enp3s0
      addresses: [192.168.10.5/24]
      routes:
        - to: default
          via: 192.168.10.1
      nameservers:
        addresses: [192.168.10.1]
      link-local: []
    iot:
      id: 20
      link: enp3s0
      link-local: []
    nas:
      id: 30
      link: enp3s0
      link-local: []
```

Only `personal` has an address, which is the VM's management IP. The `iot` and `nas` VLANs have no address, so the VM can't route to them. Setting `link-local: []` removes the automatic IPv6 link-local addresses from every interface.

Then apply it:

```sh
sudo chmod 600 /etc/netplan/01-mdns-mirror.yaml
sudo netplan apply
```

## 2. Disable forwarding

Create `/etc/sysctl.d/99-mdns-mirror.conf`:

```
net.ipv4.ip_forward = 0
net.ipv6.conf.all.forwarding = 0
```

Apply it:

```sh
sudo sysctl --system
```

## 3. Install Docker

Install Docker Engine with the Compose plugin from Docker's Ubuntu repository, and make sure it starts on boot:

```sh
sudo systemctl enable --now docker
```

## 4. Create one macvlan network per mirrored network

Each network is a macvlan on its VLAN subinterface. Docker creates the macvlan, and the container gets its own address on it.

```sh
docker network create -d macvlan --subnet 192.168.10.0/24 -o parent=personal personal_net
docker network create -d macvlan --subnet 192.168.20.0/24 -o parent=iot iot_net
docker network create -d macvlan --subnet 192.168.30.0/24 -o parent=nas nas_net
```

The `-o parent=` value is the VLAN interface name from step 1.

## 5. Compose file

Create `compose.yaml` next to your rules file. Each network is an external network created in step 4:

```yaml
services:
  mdns-mirror:
    build: .
    restart: unless-stopped
    cap_add:
      - NET_ADMIN
    command: ["--rules", "/etc/mdns-mirror/rules.yaml", "eth0", "eth1", "eth2"]
    volumes:
      - ./rules.yaml:/etc/mdns-mirror/rules.yaml:ro
    networks:
      - personal
      - iot
      - nas

networks:
  personal:
    external: true
    name: personal_net
  iot:
    external: true
    name: iot_net
  nas:
    external: true
    name: nas_net
```

`restart: unless-stopped` starts the container whenever Docker starts, so it comes back after a reboot. `cap_add: NET_ADMIN` lets the container load its firewall rules when it starts. The rules drop all traffic except mDNS.

The `command` lists the container's interface names after the rules path. Docker names the interfaces `eth0`, `eth1`, and so on, in an order you should confirm. Run `docker compose exec mdns-mirror ip -br link` after starting the container. Then make the `command` and the rule names in `rules.yaml` match what it shows.

Before starting, confirm the VLAN interfaces exist on the VM. Run this from the repository on the VM, with the VLAN interface names from step 1:

```sh
deploy/check-vlans.sh enp3s0.10 enp3s0.20 enp3s0.30
```

If any are reported missing, fix the netplan file and run `sudo netplan apply` before continuing.

Start it:

```sh
docker compose up -d
```

## 6. Verify

Check the VM's addresses. Only the management VLAN should have an IP:

```sh
ip -br addr
```

Check forwarding is off:

```sh
sysctl net.ipv4.ip_forward net.ipv6.conf.all.forwarding
```

Both should print `0`.

Check the container has an address on each network:

```sh
docker compose exec mdns-mirror ip -br addr
```

SSH to the VM at `192.168.10.5` to confirm management access still works.

## Logging

By default the container logs startup messages and errors. To log every mirror decision, add `--verbose` to the `command` list. Each decision line shows the source network, output network, message kind, delivery type, and whether the message was relayed or dropped.

## Known limitation

The VM can't reach the container over the same VLAN. This is how macvlan works. You can still SSH into the VM, and you can reach the container's mirrored networks from other hosts. If you later need the VM to talk to the container directly, add a macvlan shim on the `personal` VLAN.
