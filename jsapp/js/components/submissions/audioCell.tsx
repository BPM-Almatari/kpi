import React from 'react';
import bem, {makeBem} from 'js/bem';
import Button from 'js/components/common/button';
import MiniAudioPlayer from 'js/components/common/miniAudioPlayer';
import {goToProcessing} from 'js/components/processing/routes.utils';
import type {SubmissionAttachment} from 'js/dataInterface';
import './audioCell.scss';

bem.AudioCell = makeBem(null, 'audio-cell');

interface AudioCellProps {
  assetUid: string;
  qpath: string;
  /* submissionEditId is meta/rootUuid || _uuid */
  submissionEditId: string;
  /** Required by the mini player. */
  mediaAttachment: SubmissionAttachment;
}

/**
 * An alternative component to MediaCell for audio columns. It's a transitional
 * component created with Processing View in mind. It omits the modal.
 */
export default class AudioCell extends React.Component<AudioCellProps, {}> {
  render() {
    return (
      <bem.AudioCell>
        {this.props.mediaAttachment?.download_url &&
          <MiniAudioPlayer
            mediaURL={this.props.mediaAttachment?.download_url}
          />
        }
        <Button
          type='full'
          size='s'
          color='blue'
          endIcon='arrow-up-right'
          label={t('Open')}
          onClick={() => {
            goToProcessing(
              this.props.assetUid,
              this.props.qpath,
              this.props.submissionEditId,
            );
          }}
        />
      </bem.AudioCell>
    );
  }
}
