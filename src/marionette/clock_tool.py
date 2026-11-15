"""Read the host wall clock on demand, without network or persistent state."""
from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jsonschema import ValidationError
from qwen_agent.tools import BaseTool


class GetCurrentTime(BaseTool):
    name = 'get_current_time'
    description = (
        'Check the current date and time from the local computer clock when needed. '
        'Returns one instant in UTC and in an optional IANA timezone, including its numeric UTC offset and weekday. '
        'Default timezone is UTC. Use the contact’s supplied timezone when known; do not infer their timezone '
        'from the computer or invent one. This is a fresh observation, not a timer, alarm, scheduler or internet time check.')
    parameters = {'type': 'object', 'properties': {
        'timezone': {'type': 'string', 'description': 'IANA timezone, e.g. America/New_York. Omit for UTC.'}},
        'required': []}

    def call(self, params, **kwargs):
        try:
            args = self._verify_json_format_args(params)
            if not isinstance(args, dict) or set(args) - {'timezone'}:
                raise ValueError('Only the optional timezone field is accepted.')
            zone_name = args.get('timezone', 'UTC')
            if not isinstance(zone_name, str) or not zone_name or len(zone_name) > 128:
                raise ValueError('Use a valid IANA timezone, or omit timezone for UTC.')
            zone = ZoneInfo(zone_name)
            instant = datetime.now(timezone.utc)
            local = instant.astimezone(zone)
            return json.dumps({'status': 'ok', 'source': 'local_system_clock',
                'current_time_utc': instant.isoformat(), 'timezone': zone_name,
                'current_time': local.isoformat(),
                'weekday': ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')[local.weekday()]})
        except (ValueError, TypeError, ValidationError, ZoneInfoNotFoundError):
            return json.dumps({'status': 'error', 'error': 'Use only an optional valid IANA timezone, such as America/New_York; omit it for UTC.'})
