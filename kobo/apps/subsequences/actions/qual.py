from ..actions.base import BaseAction, ACTION_NEEDED, PASSES
from ..jsonschemas.qual_schema import DEFINITIONS as QUAL_DEFINITIONS


class QualAction(BaseAction):
    ID = 'qual'

    @classmethod
    def build_params(kls, survey_content):
        _fields = []
        for row in survey_content.get('survey', []):
            if row['type'] in ['audio', 'video']:
                _fields.append(row['name'])
        return {'values': _fields}

    def load_params(self, params):
        '''
        Action.load_params is called when the instance is initialized
        for each Asset. It will 
        '''
        self.fields = params.get('values', [])
        self.qual_survey = params.get('qual_survey', [])
        self.everything_else = params

    @classmethod
    def get_values_for_content(kls, content):
        '''
        If no "values" are defined for a given asset, then this method will
        generate a set of defaults.
        '''
        values = []
        for row in content.get('survey', []):
            if row['type'] in ['audio', 'video']:
                values.append(kls.get_qpath(kls, row))
        return values

    def modify_jsonschema(self, schema):
        definitions = schema.setdefault('definitions', {})
        definitions.update(QUAL_DEFINITIONS)

        for qual_item in self.qual_survey:
            if qual_item.get('scope') != 'by_question#survey':
                raise NotImplementedError('by_question#survey is '
                                          'the only implementation')
            item_qpath = qual_item.get('qpath')
            field_def = schema['properties'].setdefault(
                item_qpath,
                {'type': 'object',
                 'additionalProperties': False,
                 'properties': {
                    self.ID: {
                        'type': 'array',
                        'items': {
                            '$ref': '#/definitions/qual_item',
                        }
                    }
                }},
            )
        return schema
