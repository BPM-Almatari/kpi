import copy
from ..actions.base import BaseAction, ACTION_NEEDED, PASSES

class KeywordSearchAction(BaseAction):
    ID = 'keyword_search'

    '''
    @classmethod
    def build_params(kls, params, content):
        possible_transcribed_fields = []
        for row in content.get('survey', []):
            if row['type'] in ['audio', 'video']:
                possible_transcribed_fields.append(kls.get_qpath(kls, row))
        params = {'values': possible_transcribed_fields}
        return params
    '''

    @classmethod
    def get_values_for_content(kls, content):
        possible_transcribed_fields = []
        for row in content.get('survey', []):
            if row['type'] in ['audio', 'video']:
                possible_transcribed_fields.append(kls.get_qpath(kls, row))
        return possible_transcribed_fields

    def load_params(self, params):
        self.params = params

    def modify_jsonschema(self, schema):
        return {}  # FIXME

    @staticmethod
    def _traverse_object(obj, slash_separated_path):
        x = obj
        for i in slash_separated_path.split('/'):
            x = x[i]
        return x

    @staticmethod
    def _get_matching_element(lst, **query):
        # this seems inefficient
        for e in lst:
            for k, v in query.items():
                if e.get(k) != v:
                    break
            else:
                return e

    def check_submission_status(self, submission):
        # almost as much work as just redoing the counts?
        for query in self.params['by_response']:
            source = query['source']
            try:
                response = self._traverse_object(submission, source)
            except KeyError:
                continue
            qpath = source.split('/')[0]
            all_output = submission[qpath].setdefault(self.ID, [])
            this_output = self._get_matching_element(all_output, **query)
            if not this_output:
                return ACTION_NEEDED
            if (
                this_output[self.DATE_MODIFIED_FIELD]
                != response[self.DATE_MODIFIED_FIELD]
            ):
                return ACTION_NEEDED
        return PASSES

    def run_change(self, submission):
        for query in self.params['by_response']:
            source = query['source']
            try:
                response = self._traverse_object(submission, source)
            except KeyError:
                continue
            matches = 0
            for keyword in query['keywords']:
                matches += response['value'].count(keyword)
            qpath = source.split('/')[0]
            all_output = submission[qpath].setdefault(self.ID, [])
            this_output = self._get_matching_element(all_output, **query)
            if not this_output:
                this_output = copy.deepcopy(query)
                all_output.append(this_output)
            this_output['count'] = matches
            this_output[self.DATE_MODIFIED_FIELD] = response[
                self.DATE_MODIFIED_FIELD
            ]
