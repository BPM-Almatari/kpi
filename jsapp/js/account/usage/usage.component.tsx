import {when} from 'mobx';
import React, {useContext, useEffect, useMemo, useState} from 'react';
import {useLocation} from 'react-router-dom';
import type {AccountLimitDetail, LimitAmount} from 'js/account/stripe.types';
import {Limits, USAGE_TYPE} from 'js/account/stripe.types';
import {getAccountLimits} from 'js/account/stripe.api';
import subscriptionStore from 'js/account/subscriptionStore';
import LoadingSpinner from 'js/components/common/loadingSpinner';
import UsageContainer from 'js/account/usage/usageContainer';
import envStore from 'js/envStore';
import {formatDate} from 'js/utils';
import styles from './usage.module.scss';
import useWhenStripeIsEnabled from 'js/hooks/useWhenStripeIsEnabled.hook';
import {ProductsContext} from '../useProducts.hook';
import {UsageContext} from 'js/account/usage/useUsage.hook';
import {OneTimeAddOnsContext} from '../useOneTimeAddonList.hook';
import moment from 'moment';
import {YourPlan} from 'js/account/usage/yourPlan.component';
import cx from 'classnames';
import LimitNotifications from 'js/components/usageLimits/limitNotifications.component';

interface LimitState {
  storageByteRemainingLimit: LimitAmount;
  storageByteRecurringLimit: LimitAmount;
  nlpCharacterRemainingLimit: LimitAmount;
  nlpCharacterRecurringLimit: LimitAmount;
  nlpMinuteRemainingLimit: LimitAmount;
  nlpMinuteRecurringLimit: LimitAmount;
  submissionsRemainingLimit: LimitAmount;
  submissionsRecurringLimit: LimitAmount;
  isLoaded: boolean;
  stripeEnabled: boolean;
}

export default function Usage() {
  const productsContext = useContext(ProductsContext);
  const usage = useContext(UsageContext);
  const oneTimeAddOnsContext = useContext(OneTimeAddOnsContext);

  const [limits, setLimits] = useState<LimitState>({
    storageByteRemainingLimit: Limits.unlimited,
    storageByteRecurringLimit: Limits.unlimited,
    nlpCharacterRemainingLimit: Limits.unlimited,
    nlpCharacterRecurringLimit: Limits.unlimited,
    nlpMinuteRemainingLimit: Limits.unlimited,
    nlpMinuteRecurringLimit: Limits.unlimited,
    submissionsRemainingLimit: Limits.unlimited,
    submissionsRecurringLimit: Limits.unlimited,
    isLoaded: false,
    stripeEnabled: false,
  });

  const location = useLocation();

  const isFullyLoaded = useMemo(
    () =>
      usage.isLoaded &&
      (productsContext.isLoaded || !limits.stripeEnabled) &&
      limits.isLoaded &&
      oneTimeAddOnsContext.isLoaded,
    [
      usage.isLoaded,
      productsContext.isLoaded,
      limits.isLoaded,
      limits.stripeEnabled,
      oneTimeAddOnsContext.isLoaded,
    ]
  );

  const dateRange = useMemo(() => {
    let startDate: string;
    const endDate = usage.billingPeriodEnd
      ? formatDate(usage.billingPeriodEnd)
      : formatDate(moment().endOf('month').toISOString());
    switch (usage.trackingPeriod) {
      case 'year':
        startDate = formatDate(usage.currentYearStart);
        break;
      default:
        startDate = formatDate(usage.currentMonthStart);
        break;
    }
    return t('##start_date## to ##end_date##')
      .replace('##start_date##', startDate)
      .replace('##end_date##', endDate);
  }, [
    usage.currentYearStart,
    usage.currentMonthStart,
    usage.billingPeriodEnd,
    usage.trackingPeriod,
  ]);

  // check if stripe is enabled - if so, get limit data
  useEffect(() => {
    const getLimits = async () => {
      await when(() => envStore.isReady);
      let limits: AccountLimitDetail;
      if (envStore.data.stripe_public_key) {
        limits = await getAccountLimits(
          productsContext.products,
          oneTimeAddOnsContext.addons
        );
      } else {
        setLimits((prevState) => {
          return {
            ...prevState,
            isLoaded: true,
          };
        });
        return;
      }

      setLimits((prevState) => {
        return {
          ...prevState,
          storageByteRemainingLimit: limits.remainingLimits.storage_bytes_limit,
          storageByteRecurringLimit: limits.recurringLimits.storage_bytes_limit,
          nlpCharacterRemainingLimit:
            limits.remainingLimits.nlp_character_limit,
          nlpCharacterRecurringLimit:
            limits.recurringLimits.nlp_character_limit,
          nlpMinuteRemainingLimit:
            typeof limits.remainingLimits.nlp_seconds_limit === 'number'
              ? limits.remainingLimits.nlp_seconds_limit / 60
              : limits.remainingLimits.nlp_seconds_limit,
          nlpMinuteRecurringLimit:
            typeof limits.recurringLimits.nlp_seconds_limit === 'number'
              ? limits.recurringLimits.nlp_seconds_limit / 60
              : limits.recurringLimits.nlp_seconds_limit,
          submissionsRemainingLimit: limits.remainingLimits.submission_limit,
          submissionsRecurringLimit: limits.recurringLimits.submission_limit,
          isLoaded: true,
          stripeEnabled: true,
        };
      });
    };

    getLimits();
  }, [productsContext.isLoaded, oneTimeAddOnsContext.isLoaded]);

  function filterAddOns(type: USAGE_TYPE) {
    const availableAddons = oneTimeAddOnsContext.addons.filter(
      (addon) => addon.is_available
    );
    
    // Find the relevant addons, but first check and make sure add-on
    // limits aren't superceded by an "unlimited" usage limit.
    switch (type) {
      case USAGE_TYPE.SUBMISSIONS:
        return limits.submissionsRecurringLimit !== Limits.unlimited
          ? availableAddons.filter(
              (addon) => addon.total_usage_limits.submission_limit
            )
          : [];
      case USAGE_TYPE.TRANSCRIPTION:
        return limits.nlpMinuteRecurringLimit !== Limits.unlimited
          ? availableAddons.filter(
              (addon) => addon.total_usage_limits.asr_seconds_limit
            )
          : [];
      case USAGE_TYPE.TRANSLATION:
        return limits.nlpCharacterRecurringLimit !== Limits.unlimited
          ? availableAddons.filter(
              (addon) => addon.total_usage_limits.mt_characters_limit
            )
          : [];
      default:
        return [];
    }
  }

  const useAddonsLayout = useMemo(() => {
    let result = false;
    for (const type of [
      USAGE_TYPE.STORAGE,
      USAGE_TYPE.SUBMISSIONS,
      USAGE_TYPE.TRANSCRIPTION,
      USAGE_TYPE.TRANSLATION,
    ]) {
      const relevantAddons = filterAddOns(type);
      if (relevantAddons.length > 0) {
        result = true;
      }
    }
    return result;
  }, [oneTimeAddOnsContext.isLoaded, limits.isLoaded]);

  // if stripe is enabled, load fresh subscription info whenever we navigate to this route
  useWhenStripeIsEnabled(() => {
    subscriptionStore.fetchSubscriptionInfo();
  }, [location]);

  if (!isFullyLoaded) {
    return <LoadingSpinner />;
  }

  return (
    <div className={styles.root}>
      <LimitNotifications accountPage />
      <header className={styles.header}>
        <h2 className={styles.headerText}>{t('Your usage')}</h2>
        {typeof usage.lastUpdated === 'string' && (
          <p className={styles.updated}>
            {t('Last update: ##LAST_UPDATE_TIME##').replace(
              '##LAST_UPDATE_TIME##',
              usage.lastUpdated
            )}
          </p>
        )}
      </header>
      {limits.stripeEnabled && <YourPlan />}
      <div className={styles.row}>
        <div className={cx(styles.row, styles.subrow)}>
          <div className={styles.box}>
            <span>
              <strong className={styles.title}>{t('Submissions')}</strong>
              <time className={styles.date}>{dateRange}</time>
            </span>
            <UsageContainer
              usage={usage.submissions}
              remainingLimit={limits.submissionsRemainingLimit}
              recurringLimit={limits.submissionsRecurringLimit}
              oneTimeAddons={filterAddOns(USAGE_TYPE.SUBMISSIONS)}
              useAddonLayout={useAddonsLayout}
              period={usage.trackingPeriod}
              type={USAGE_TYPE.SUBMISSIONS}
            />
          </div>
          <div className={styles.box}>
            <span>
              <strong className={styles.title}>{t('Storage')}</strong>
              <div className={styles.date}>{t('per account')}</div>
            </span>
            <UsageContainer
              usage={usage.storage}
              remainingLimit={limits.storageByteRemainingLimit}
              recurringLimit={limits.storageByteRecurringLimit}
              oneTimeAddons={filterAddOns(USAGE_TYPE.STORAGE)}
              useAddonLayout={useAddonsLayout}
              period={usage.trackingPeriod}
              label={t('Total')}
              type={USAGE_TYPE.STORAGE}
            />
          </div>
        </div>
        <div className={cx(styles.row, styles.subrow)}>
          <div className={styles.box}>
            <span>
              <strong className={styles.title}>
                {t('Transcription minutes')}
              </strong>
              <time className={styles.date}>{dateRange}</time>
            </span>
            <UsageContainer
              usage={usage.transcriptionMinutes}
              remainingLimit={limits.nlpMinuteRemainingLimit}
              recurringLimit={limits.nlpMinuteRecurringLimit}
              oneTimeAddons={filterAddOns(USAGE_TYPE.TRANSCRIPTION)}
              useAddonLayout={useAddonsLayout}
              period={usage.trackingPeriod}
              type={USAGE_TYPE.TRANSCRIPTION}
            />
          </div>
          <div className={styles.box}>
            <span>
              <strong className={styles.title}>
                {t('Translation characters')}
              </strong>
              <time className={styles.date}>{dateRange}</time>
            </span>
            <UsageContainer
              usage={usage.translationChars}
              remainingLimit={limits.nlpCharacterRemainingLimit}
              recurringLimit={limits.nlpCharacterRecurringLimit}
              oneTimeAddons={filterAddOns(USAGE_TYPE.TRANSLATION)}
              useAddonLayout={useAddonsLayout}
              period={usage.trackingPeriod}
              type={USAGE_TYPE.TRANSLATION}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
