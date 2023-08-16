import React, {useContext, useState} from 'react';
import CommonHeader from './commonHeader.component';
import AnalysisQuestionsContext from 'js/components/processing/analysis/analysisQuestions.context';
import {
  findQuestion,
  getQuestionTypeDefinition,
  updateResponseAndReducer,
} from 'js/components/processing/analysis/utils';
import type {MultiCheckboxItem} from 'js/components/common/multiCheckbox';
import MultiCheckbox from 'js/components/common/multiCheckbox';
import commonStyles from './common.module.scss';

interface SelectMultipleResponseFormProps {
  uuid: string;
}

export default function SelectMultipleResponseForm(
  props: SelectMultipleResponseFormProps
) {
  const analysisQuestions = useContext(AnalysisQuestionsContext);

  // Get the question data from state (with safety check)
  const question = findQuestion(props.uuid, analysisQuestions?.state);
  if (!question) {
    return null;
  }

  // Get the question definition (with safety check)
  const qaDefinition = getQuestionTypeDefinition(question.type);
  if (!qaDefinition) {
    return null;
  }

  // This will either be an existing list of selected choices, or an empty list.
  const initialResponse = Array.isArray(question.response) ? question.response : [];

  const [response, setResponse] = useState<string[]>(initialResponse);

  function onCheckboxesChange(items: MultiCheckboxItem[]) {
    const newResponse = items
      .filter((item) => item.checked)
      .map((item) => item.name);

    // Update local state
    setResponse(newResponse);

    // Update endpoint and reducer
    updateResponseAndReducer(
      analysisQuestions?.dispatch,
      props.uuid,
      question?.type,
      newResponse
    );
  }

  function getCheckboxes(): MultiCheckboxItem[] {
    if (question?.additionalFields?.choices) {
      return question?.additionalFields?.choices.map((choice) => {
        return {
          name: choice.uuid,
          label: choice.labels._default,
          checked: response.includes(choice.uuid),
        };
      });
    }
    return [];
  }

  return (
    <>
      <CommonHeader uuid={props.uuid} />

      <section className={commonStyles.content}>
        <MultiCheckbox
          type='bare'
          items={getCheckboxes()}
          onChange={onCheckboxesChange}
          disabled={analysisQuestions?.state.isPending}
        />
      </section>
    </>
  );
}