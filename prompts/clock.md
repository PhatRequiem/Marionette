## get_current_time

You can check the current date and time on demand. The tool returns the full date, time, numeric UTC offset and weekday for the requested timezone, plus the same instant in UTC.

Use get_current_time when you need a fresh current date or time, including when the timestamp attached to the user's message may be stale. For a question asking the current date or time, call this tool before answering. Prefer a timezone explicitly requested by the user, otherwise use the contact's supplied IANA timezone when known; otherwise use UTC and label it as UTC. Do not guess the user's timezone. The result is one observation of the local computer clock, not a continuously running clock or independent verification that the system clock is accurate. This tool cannot schedule reminders or wake you later. Old clock results in conversation history are historical; call again when a fresh reading matters.
