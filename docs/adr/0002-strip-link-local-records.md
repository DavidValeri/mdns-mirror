# Strip link-local records and re-encode relayed packets

The mirror removes link-local A and AAAA records from packets it relays, as Avahi does, because those addresses are valid only on their home network. Removing records means rebuilding the packet, so the mirror decodes every name and writes it uncompressed. Packets with nothing to remove are forwarded byte-for-byte. We chose this over relaying packets unchanged, which would break connections across networks.
