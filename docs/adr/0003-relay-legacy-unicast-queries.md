# Relay legacy unicast queries with relay-chosen IDs

Legacy unicast queries, sent from a port other than 5353, are relayed by sending them from an ephemeral socket on each output network with a relay-chosen ID, so responders reply to the relay rather than to the original querier. The relay keeps a short-lived table mapping each ID to the querier and restores the original ID on the reply, as Avahi does. We chose this over sending legacy queries from port 5353 because that would turn them into ordinary multicast queries, and responders would answer them by multicast instead of unicast.
