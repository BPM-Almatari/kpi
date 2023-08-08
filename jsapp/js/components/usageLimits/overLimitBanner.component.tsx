import React, {useEffect, useState} from 'react';
import Button from 'js/components/common/button';
import {getAllExceedingLimits, getPlanInterval} from './usageCalculations';
import {ACCOUNT_ROUTES} from 'js/account/routes';
import {useNavigate} from 'react-router-dom';
import styles from './overLimitBanner.module.scss';
import Icon from 'js/components/common/icon';

function OverLimitBanner() {
  const navigate = useNavigate();
  const interval = getPlanInterval();

  const limitsLength = getAllExceedingLimits().length;

  return (
    <div className={styles.limitBannerContainer}>
      <Icon name='alert' size='m' color='red' />
      <div className={styles.bannerContent}>
        {t('You have surpassed your')}{' '}
        <strong>
          {`${interval}ly`}{' '}
          {getAllExceedingLimits().map((item, i) => (
            <span key={i}>
              {i > 0 && ', '}
              {i === limitsLength - 1 && i > 0 && 'and '}
              {item}
            </span>
          ))}{' '}
          {t('limit')}
          {limitsLength > 1 && 's'}{' '}
        </strong>
        {t(
          '. Please upgrade to a plan with a larger capacity to continue collecting data this ##PERIOD##. You can'
        ).replace(/##PERIOD##/g, interval)
        }{' '}
        <a
          aria-label={t('review your usage here')}
          href={`#${ACCOUNT_ROUTES.USAGE}`}
          className={styles.bannerLink}
        >
          {t('review your usage here')}
        </a>
        {t(', or learn more about the KoboToolbox limits and plans in our ')}
        <a
          aria-label={t('paid plans page')}
          href={'https://www.kobotoolbox.org/how-it-works/'}
          className={styles.bannerLink}
        >
          {t('paid plans page')}
        </a>
        .
      </div>
      <Button
        type='full'
        color='dark-red'
        endIcon='arrow-right'
        size='s'
        label={t('Upgrade now')}
        onClick={() => navigate(ACCOUNT_ROUTES.PLAN)}
        aria-label={t('upgrade now')}
        classNames={[styles.bannerBtn]}
      />
    </div>
  );
}

export default OverLimitBanner;