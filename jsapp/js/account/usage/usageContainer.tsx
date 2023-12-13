import classnames from 'classnames';
import prettyBytes from 'pretty-bytes';
import React from 'react';
import type {LimitAmount, RecurringInterval} from 'js/account/stripe.types';
import Icon from 'js/components/common/icon';
import styles from 'js/account/usage/usageContainer.module.scss';
import {USAGE_WARNING_RATIO} from 'js/constants';
import AriaText from 'js/components/common/ariaText';
import {Limits} from 'js/account/stripe.types';

interface UsageContainerProps {
  usage: number;
  limit: LimitAmount;
  period: RecurringInterval;
  label?: string;
  isStorage?: boolean;
}

const UsageContainer = ({
  usage,
  limit,
  period,
  label = undefined,
  isStorage = false,
}: UsageContainerProps) => {
  let limitRatio = 0;
  if (limit !== Limits.unlimited && limit) {
    limitRatio = usage / limit;
  }
  const isOverLimit = limitRatio >= 1;
  const isNearingLimit = !isOverLimit && limitRatio > USAGE_WARNING_RATIO;
  return (
    <div className={styles.usage}>
      <strong className={styles.description}>
        {label || (period === 'month' ? t('Monthly') : t('Yearly'))}
      </strong>
      <div
        className={classnames(styles.usageRow, {
          [styles.warning]: isNearingLimit,
          [styles.overlimit]: isOverLimit,
        })}
      >
        {isNearingLimit && <Icon name='warning' color='amber' size='m' />}
        {isOverLimit && <Icon name='warning' color='red' size='m' />}
        <strong>
          {isStorage ? prettyBytes(usage) : usage.toLocaleString()}
        </strong>
        {limit !== Limits.unlimited && limit && (
          <>
            {' '}
            <AriaText uiText='/' screenReaderText={t('used out of')} />{' '}
            <span>
              {isStorage ? prettyBytes(limit) : limit.toLocaleString()}
            </span>
          </>
        )}
      </div>
    </div>
  );
};

export default UsageContainer;
