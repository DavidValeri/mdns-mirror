"""Reading and rewriting mDNS packets.

Two jobs live here:

- classify() reads only what the relay needs to decide: whether a packet is
  a query or an advertisement (the QR bit), and whether a query asks for a
  unicast reply (the QU bit).
- strip_link_local() removes address records that are only valid on their
  own network. It only rebuilds a packet when there is something to remove.
"""

import struct

TYPE_A = 1
TYPE_CNAME = 5
TYPE_NS = 2
TYPE_PTR = 12
TYPE_AAAA = 28
TYPE_SRV = 33

# Types whose rdata is a domain name (or starts with one, for SRV).
_NAME_RDATA = {TYPE_PTR, TYPE_CNAME, TYPE_NS}


def _skip_name(data, offset):
    """Return the offset just past a DNS name.

    A name is a sequence of length-prefixed labels ending in a zero byte, or
    a two-byte compression pointer (top bits 11) that ends the name.

    Args:
        data: The raw packet bytes.
        offset: Where the name starts.

    Returns:
        The offset of the first byte after the name.
    """
    while True:
        length = data[offset]
        if length == 0:
            return offset + 1
        if length & 0xC0 == 0xC0:
            return offset + 2
        offset += 1 + length


def classify(data):
    """Work out whether a packet is a query or an advertisement, and its QU bit.

    Args:
        data: The raw bytes of one mDNS packet.

    Returns:
        A (kind, qu) tuple. `kind` is "query" or "advertisement". `qu` is
        True if any question has the QU bit set.

    Raises:
        ValueError: If the packet is shorter than a DNS header.
        IndexError: If the question section is truncated. Callers skip
            such packets.
    """
    if len(data) < 12:
        raise ValueError("short mDNS packet")
    flags = int.from_bytes(data[2:4], "big")
    question_count = int.from_bytes(data[4:6], "big")
    kind = "advertisement" if flags & 0x8000 else "query"
    qu = False
    offset = 12
    for _ in range(question_count):
        offset = _skip_name(data, offset)
        # The top bit of the question class is the QU bit.
        qclass = int.from_bytes(data[offset + 2 : offset + 4], "big")
        qu = qu or bool(qclass & 0x8000)
        offset += 4
    return kind, qu


def _read_name(data, offset):
    """Decode a possibly compressed name, following pointers.

    Args:
        data: The whole packet. Compression pointers are offsets into it.
        offset: Where the name starts.

    Returns:
        A (labels, end) tuple. `labels` is a list of label bytes. `end` is
        the offset just past the name as it appears at `offset`, not where
        any pointer leads.

    Raises:
        ValueError: If the name is truncated, malformed, or loops.
    """
    labels = []
    end = None
    jumps = 0
    while True:
        if offset >= len(data):
            raise ValueError("name runs past the end of the packet")
        length = data[offset]
        if length == 0:
            if end is None:
                end = offset + 1
            return labels, end
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(data):
                raise ValueError("compression pointer runs past the end of the packet")
            if end is None:
                end = offset + 2
            offset = ((length & 0x3F) << 8) | data[offset + 1]
            jumps += 1
            if jumps > 127:
                raise ValueError("compression pointers loop")
            continue
        if length & 0xC0:
            raise ValueError("unsupported label type")
        stop = offset + 1 + length
        if stop > len(data):
            raise ValueError("label runs past the end of the packet")
        labels.append(data[offset + 1 : stop])
        offset = stop


def _encode_name(labels):
    """Encode labels as an uncompressed DNS name.

    Args:
        labels: A list of label bytes, without the trailing zero.

    Returns:
        The encoded name, ending with the zero-length root label.
    """
    return b"".join(bytes([len(label)]) + label for label in labels) + b"\0"


def _is_link_local(rtype, rdata):
    """Check whether an A or AAAA record holds a link-local address.

    Link-local addresses are 169.254.0.0/16 for IPv4 and fe80::/10 for IPv6.

    Args:
        rtype: The record type.
        rdata: The record's raw address bytes.

    Returns:
        True if the record is a link-local address record.
    """
    if rtype == TYPE_A:
        return len(rdata) == 4 and rdata[:2] == b"\xa9\xfe"
    if rtype == TYPE_AAAA:
        return len(rdata) == 16 and rdata[0] == 0xFE and rdata[1] & 0xC0 == 0x80
    return False


def _rdata(data, rtype, start, end):
    """Return rdata in a form that is safe to copy into a new packet.

    Names inside rdata can be compressed in the original packet, so they're
    decoded and written out uncompressed. Other rdata is copied as-is.

    Args:
        data: The whole original packet.
        rtype: The record type.
        start: Offset where the rdata starts.
        end: Offset where the rdata ends.

    Returns:
        The rdata bytes, with any names uncompressed.
    """
    if rtype in _NAME_RDATA:
        labels, _ = _read_name(data, start)
        return _encode_name(labels)
    if rtype == TYPE_SRV:
        # Priority, weight, and port take 6 bytes; the target name follows.
        labels, _ = _read_name(data, start + 6)
        return data[start : start + 6] + _encode_name(labels)
    return data[start:end]


def strip_link_local(data):
    """Remove link-local A and AAAA records from the answer and additional sections.

    Avahi does the same when it reflects. The packet is returned as-is when
    there's nothing to remove, so unaffected traffic is byte-identical.
    When something is removed, the packet is rebuilt with every name written
    uncompressed and the record counts updated.

    Args:
        data: The raw bytes of one mDNS packet.

    Returns:
        The packet bytes to forward.

    Raises:
        ValueError: If the packet is malformed.
    """
    if len(data) < 12:
        raise ValueError("short mDNS packet")
    try:
        return _strip(data)
    except (IndexError, struct.error) as error:
        raise ValueError("malformed mDNS packet") from error


def _strip(data):
    """Do the work for strip_link_local. Callers handle malformed-packet errors."""
    packet_id, flags, question_count, answer_count, authority_count, additional_count = struct.unpack_from("!HHHHHH", data, 0)
    offset = 12
    questions = []
    for _ in range(question_count):
        labels, offset = _read_name(data, offset)
        qtype, qclass = struct.unpack_from("!HH", data, offset)
        offset += 4
        questions.append(_encode_name(labels) + struct.pack("!HH", qtype, qclass))

    sections = {"answers": [], "authority": [], "additional": []}
    dropped = 0
    for section, count in (("answers", answer_count), ("authority", authority_count), ("additional", additional_count)):
        for _ in range(count):
            labels, offset = _read_name(data, offset)
            rtype, rclass, ttl, rdlength = struct.unpack_from("!HHIH", data, offset)
            offset += 10
            end = offset + rdlength
            if end > len(data):
                raise ValueError("record data runs past the end of the packet")
            # Authority records are never link-local records, so they're kept.
            if section != "authority" and _is_link_local(rtype, data[offset:end]):
                dropped += 1
            else:
                rdata = _rdata(data, rtype, offset, end)
                sections[section].append(
                    _encode_name(labels) + struct.pack("!HHIH", rtype, rclass, ttl, len(rdata)) + rdata
                )
            offset = end

    if dropped == 0:
        return data

    header = struct.pack(
        "!HHHHHH",
        packet_id,
        flags,
        len(questions),
        len(sections["answers"]),
        len(sections["authority"]),
        len(sections["additional"]),
    )
    return header + b"".join(questions) + b"".join(
        sections["answers"] + sections["authority"] + sections["additional"]
    )
