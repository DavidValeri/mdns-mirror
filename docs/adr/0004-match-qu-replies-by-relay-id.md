# Match QU replies by relay-chosen ID, not querier ID

A QU query is relayed with a relay-chosen ID, shared across output networks and unique among live entries, instead of the querier's own ID. The relay restores the original ID on the reply, as it already does for legacy unicast queries. We chose this over matching replies on the querier's ID because querier IDs are often 0 or predictable, so an unrelated multicast message could be unicast to a querier that never asked for it. The relay never picks ID 0 for a QU query, since most advertisements carry it.
