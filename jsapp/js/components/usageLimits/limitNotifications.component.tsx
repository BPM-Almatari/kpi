import LimitBanner from 'js/components/usageLimits/overLimitBanner.component';
import LimitModal from 'js/components/usageLimits/overLimitModal.component';
import React, {useState} from 'react';
import {Cookies} from 'react-cookie';
import {
  getAllExceedingLimits,
  getPlanInterval,
} from 'js/components/usageLimits/usageCalculations';
import useWhenStripeIsEnabled from 'js/hooks/useWhenStripeIsEnabled.hook';

const cookies = new Cookies();

interface LimitNotificationsProps {
  useModal?: boolean;
  usagePage?: boolean;
}

const LimitNotifications = ({
  useModal = false,
  usagePage = false,
}: LimitNotificationsProps) => {
  const [showModal, setShowModal] = useState(false);
  const [dismissed, setDismissed] = useState(!useModal);
  const [stripeEnabled, setStripeEnabled] = useState(false);

  const limits = getAllExceedingLimits();
  const interval = getPlanInterval();

  useWhenStripeIsEnabled(() => {
    setStripeEnabled(true);
    // only check cookies if we're displaying a modal
    if (!useModal) {
      return;
    }
    const limitsCookie = cookies.get('kpiOverLimitsCookie');
    if (
      limitsCookie === undefined &&
      (limits.exceedList.includes('storage') ||
        limits.exceedList.includes('submission'))
    ) {
      setShowModal(true);
    }
    if (limitsCookie) {
      setDismissed(true);
    }
  }, [limits]);

  const modalDismissed = () => {
    setDismissed(true);
    const dateNow = new Date();
    const expireDate = new Date(dateNow.setDate(dateNow.getDate() + 1));
    cookies.set('kpiOverLimitsCookie', {
      expires: expireDate,
    });
  };

  if (!stripeEnabled) {
    return null;
  }

  return (
    <>
      {dismissed && (
        <LimitBanner
          interval={interval}
          limits={limits.exceedList}
          usagePage={usagePage}
        />
      )}
      {!limits.exceedList.length && (
        <LimitBanner
          warning
          interval={interval}
          limits={limits.warningList}
          usagePage={usagePage}
        />
      )}
      {useModal && (
        <LimitModal
          show={showModal}
          limits={limits.exceedList}
          interval={interval}
          dismissed={modalDismissed}
        />
      )}
    </>
  );
};

export default LimitNotifications;
