import React, { useContext } from 'react';
import AnalysisQuestionsContext from './analysisQuestions.context';
import styles from './analysisHeader.module.scss';
import Button from 'js/components/common/button';
import KoboDropdown from 'js/components/common/koboDropdown';
import { ANALYSIS_QUESTION_TYPES } from './constants';
import type { AnalysisQuestionTypeDefinition } from './constants';
import Icon from 'js/components/common/icon';
import assetStore from 'jsapp/js/assetStore';
import singleProcessingStore from 'js/components/processing/singleProcessingStore';
import { userCan } from 'js/components/permissions/utils';
import classNames from 'classnames';

export default function AnalysisHeader() {
  const analysisQuestions = useContext(AnalysisQuestionsContext);
  if (!analysisQuestions) {
    return null;
  }

  const manualTypes = Object.values(ANALYSIS_QUESTION_TYPES).filter(
    (definition) => !definition.isAutomated
  );
  const automatedTypes = Object.values(ANALYSIS_QUESTION_TYPES).filter(
    (definition) => definition.isAutomated
  );

  const hasManagePermissions = (() => {
    const asset = assetStore.getAsset(singleProcessingStore.currentAssetUid);
    return userCan('manage_asset', asset);
  })();

  function renderQuestionTypeButton(definition: AnalysisQuestionTypeDefinition) {
    return (
      <li
        className={classNames({
          [styles.addQuestionMenuButton]: true,
          // We want to disable the Keyword Search question type when there is
          // no transcript or translation.
          [styles.addQuestionMenuButtonDisabled]:
            definition.type === 'qual_auto_keyword_count' &&
            singleProcessingStore.getTranscript() === undefined &&
            singleProcessingStore.getTranslations().length === 0,
        })}
        key={definition.type}
        onClick={() => {
          analysisQuestions?.dispatch({
            type: 'addQuestion',
            payload: { type: definition.type },
          });
        }}
        tabIndex={0}
      >
        <Icon name={definition.icon} />
        <label>{definition.label}</label>
      </li>
    );
  }

  return (
    <header className={styles.root}>
      <KoboDropdown
        placement={'down-left'}
        hideOnMenuClick
        triggerContent={
          <Button
            type='full'
            color='blue'
            size='m'
            startIcon='plus'
            label={t('Add question')}
          />
        }
        menuContent={
          <menu className={styles.addQuestionMenu}>
            {manualTypes.map(renderQuestionTypeButton)}
            {automatedTypes.length > 0 && (
              <>
                <li>
                  <h2>{t('Automated analysis')}</h2>
                </li>
                {automatedTypes.map(renderQuestionTypeButton)}
              </>
            )}
          </menu>
        }
        name='qualitative_analysis_add_question'
        // We only allow editing one question at a time, so adding new is not
        // possible until user stops editing
        isDisabled={
          !hasManagePermissions ||
          analysisQuestions?.state.questionsBeingEdited.length !== 0
        }
      />

      <span>
        {!analysisQuestions.state.isPending &&
          analysisQuestions.state.changesDetected &&
          t('Unsaved changes')
        }
        {analysisQuestions.state.isPending && t('Saving…')}
        {!analysisQuestions.state.changesDetected &&
          !analysisQuestions.state.isPending &&
          t('Saved')
        }
      </span>
    </header>
  );
}
