import styles from "js/components/usageContainer.module.scss";
import classnames from "classnames";
import Icon from "js/components/common/icon";
import prettyBytes from "pretty-bytes";
import React from "react";
import {RecurringInterval} from "js/account/stripe.api";

interface UsageContainerProps {
  usage: number;
  limit: number|'unlimited';
  label?: string;
  isStorage?: boolean;
  period: RecurringInterval;
}

const WARNING_THRESHOLD_RATIO = 0.8;

const UsageContainer = ({
  usage, limit, period, label = undefined, isStorage = false,
}: UsageContainerProps) => {
  let limitRatio = 0;
  if (limit !== 'unlimited' && limit) {
    limitRatio = usage / limit;
  }
  const isOverLimit = limitRatio > 1;
  const isNearingLimit = !isOverLimit && limitRatio > WARNING_THRESHOLD_RATIO;
  return (
    <div className={styles.usage}>
        <strong className={styles.description}>
          {label ||
            (period === RecurringInterval.Month ? t('Monthly') : t('Yearly'))
          }
        </strong>
      {!usage && <span>-</span>}
      {Boolean(usage) && (
        <div className={classnames(styles.usageRow,
          {
            [styles.warning]: isNearingLimit,
            [styles.overlimit]: isOverLimit,
          },
        )}>
          {isNearingLimit &&
            <Icon name={'warning'} color={'amber'} size={'m'}/>
          }
          {isOverLimit &&
            <Icon name={'warning'} color={'red'} size={'m'}/>
          }
          <strong>{isStorage ? prettyBytes(usage) : usage.toLocaleString()}</strong>
          {(limit !== 'unlimited' && limit) &&
            <>
              <span aria-hidden> / </span>
              <span className={styles.visuallyHidden}>
                {t('used out of')}
              </span>
              <span>{isStorage ? prettyBytes(limit) : limit.toLocaleString()}</span>
            </>
          }
        </div>
      )}
    </div>
  );
};

export default UsageContainer;
