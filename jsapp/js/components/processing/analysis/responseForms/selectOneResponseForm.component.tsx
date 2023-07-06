import React, {useContext, useState} from 'react';
import CommonHeader from './commonHeader.component';
import AnalysisQuestionsContext from 'js/components/processing/analysis/analysisQuestions.context';
import {
  findQuestion,
  getQuestionTypeDefinition,
  quietlyUpdateResponse,
} from 'js/components/processing/analysis/utils';
import Radio from 'js/components/common/radio';
import type {RadioOption} from 'js/components/common/radio';
import commonStyles from './common.module.scss';
import classNames from 'classnames';
import styles from './selectOneResponseForm.module.scss';

interface SelectOneResponseFormProps {
  uuid: string;
}

export default function SelectOneResponseForm(
  props: SelectOneResponseFormProps
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

  const [response, setResponse] = useState<string>(question.response);

  function onRadioChange(newResponse: string) {
    setResponse(newResponse);

    quietlyUpdateResponse(
      analysisQuestions?.state,
      analysisQuestions?.dispatch,
      props.uuid,
      newResponse
    );
  }

  function getOptions(): RadioOption[] {
    if (question?.additionalFields?.choices) {
      return question?.additionalFields?.choices.map((choice) => {
        return {
          value: choice.uuid,
          label: choice.label,
        };
      });
    }
    return [];
  }

  return (
    <>
      <CommonHeader uuid={props.uuid} />

      <section
        className={classNames([commonStyles.content, styles.radioWrapper])}
      >
        <Radio
          options={getOptions()}
          name={question.labels._default}
          onChange={onRadioChange}
          selected={response}
          isClearable
          isDisabled={analysisQuestions?.state.isPending}
        />
      </section>
    </>
  );
}
