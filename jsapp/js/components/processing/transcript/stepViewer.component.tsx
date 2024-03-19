import React from 'react';
import Button from 'js/components/common/button';
import singleProcessingStore from 'js/components/processing/singleProcessingStore';
import HeaderLanguageAndDate from './headerLanguageAndDate.component';
import {destroyConfirm} from 'js/alertify';
import bodyStyles from 'js/components/processing/processingBody.module.scss';

export default function StepViewer() {
  function openEditor() {
    const transcript = singleProcessingStore.getTranscript();
    if (transcript) {
      // Make new draft using existing transcript.
      singleProcessingStore.setTranscriptDraft(transcript);
    }
  }

  function deleteTranscript() {
    destroyConfirm(
      singleProcessingStore.deleteTranscript.bind(singleProcessingStore),
      t('Delete transcript?')
    );
  }

  return (
    <div className={bodyStyles.root}>
      <header className={bodyStyles.transxHeader}>
        <HeaderLanguageAndDate />

        <nav className={bodyStyles.transxHeaderButtons}>
          <Button
            type='bare'
            color='storm'
            size='s'
            startIcon='edit'
            onClick={openEditor}
            tooltip={t('Edit')}
            isDisabled={singleProcessingStore.data.isFetchingData}
          />

          <Button
            type='bare'
            color='storm'
            size='s'
            startIcon='trash'
            onClick={deleteTranscript}
            tooltip={t('Delete')}
            isPending={singleProcessingStore.data.isFetchingData}
          />
        </nav>
      </header>

      <article className={bodyStyles.text}>
        {singleProcessingStore.getTranscript()?.value}
      </article>
    </div>
  );
}
