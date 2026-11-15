"""Current-contact profile editing with an application-enforced field allowlist."""
import json
from jsonschema import ValidationError
from qwen_agent.tools import BaseTool


class UpdateContactProfile(BaseTool):
    name = 'update_contact_profile'
    description = (
        'Update the CURRENT contact’s structured name, preferred_name, or timezone from information they provide. '
        'Use preferred_name for "call me Jack"; name is the display label, not necessarily a preference. '
        'An unset preferred_name is unknown, not the display name. Explicit preferences need no repeated confirmation. '
        'Omitted fields stay unchanged; null clears preferred_name or timezone. Use an explicit IANA timezone; do not guess. '
        'Other lasting facts belong in update_contact_notes. This does not edit the vault or your own identity. '
        'UUID, linked accounts, owner status, terminal access, and timestamps cannot be supplied or edited. '
        'The application maintains updated_at. Report changes only after success is true; returned profile fields '
        'supersede earlier sender metadata and are supplied on the next turn.')
    parameters = {'type': 'object', 'properties': {
        'name': {'type': 'string', 'minLength': 1, 'maxLength': 80,
                 'description': 'Unique contact display name. Omit to preserve.'},
        'preferred_name': {'type': ['string', 'null'], 'minLength': 1, 'maxLength': 80,
                           'description': 'Explicit preferred form of address, or null to clear.'},
        'timezone': {'type': ['string', 'null'],
                     'description': 'Explicit IANA timezone, or null to clear.'}},
        'required': []}

    def __init__(self, profiles, identity):
        super().__init__()
        self.profiles = profiles
        self.contact_uuid = identity['contact_uuid']

    def call(self, params, **kwargs):
        try:
            fields = self._verify_json_format_args(params)
            profile = self.profiles.update_fields(self.contact_uuid, fields)
            return json.dumps({'success': True, 'profile': profile})
        except (ValueError, ValidationError, OSError) as error:
            return json.dumps({'success': False, 'error': str(error)})
