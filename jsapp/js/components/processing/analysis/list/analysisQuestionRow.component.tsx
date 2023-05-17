import React, {useContext} from 'react';
import AnalysisQuestionsContext from '../analysisQuestions.context';
import AnalysisQuestionEditor from '../editors/analysisQuestionEditor.component';
import DefaultResponseForm from '../responseForms/defaultResponseForm.component';
import KeywordSearchResponseForm from '../responseForms/keywordSearchResponseForm.component';
import SelectMultipleResponseForm from '../responseForms/selectMultipleResponseForm.component';
import SelectOneResponseForm from '../responseForms/selectOneResponseForm.component';
import TagsResponseForm from '../responseForms/tagsResponseForm.component';
import CommonHeader from '../responseForms/commonHeader.component';
import styles from './analysisQuestionRow.module.scss';
import type {AnalysisQuestion} from '../constants';
import Icon from 'js/components/common/icon';

export interface RowProps {
  question: AnalysisQuestion;
}

export default function Row(props: RowProps) {
  const analysisQuestions = useContext(AnalysisQuestionsContext);

  if (!analysisQuestions) {
    return null;
  }

  function renderItem(question: AnalysisQuestion) {
    if (analysisQuestions?.state.questionsBeingEdited.includes(question.uid)) {
      return <AnalysisQuestionEditor uid={question.uid} />;
    } else {
      switch (question.type) {
        case 'qual_auto_keyword_count': {
          return <KeywordSearchResponseForm uid={question.uid} />;
        }
        case 'qual_note': {
          // This question type doesn't have any response
          return <CommonHeader uid={question.uid} />;
        }
        case 'qual_select_multiple': {
          return <SelectMultipleResponseForm uid={question.uid} />;
        }
        case 'qual_select_one': {
          return <SelectOneResponseForm uid={question.uid} />;
        }
        case 'qual_tags': {
          return <TagsResponseForm uid={question.uid} />;
        }
        default: {
          return <DefaultResponseForm uid={question.uid} />;
        }
      }
    }
  }

  return (
    <li className={styles.root}>
      <div className={styles.dragHandle}>
        <Icon name='drag-handle' size='xs' />
      </div>

      <div className={styles.content}>{renderItem(props.question)}</div>
    </li>
  );
}
