import {when} from 'mobx';

import {ACTIVE_STRIPE_STATUSES} from 'js/constants';
import envStore from 'js/envStore';
import type {SubscriptionInfo} from 'js/account/subscriptionStore';
import subscriptionStore from 'js/account/subscriptionStore';
import type {
  BasePrice,
  ChangePlan,
  Product,
  Checkout,
} from 'js/account/stripe.api';
import {notify} from 'js/utils';
import {ChangePlanStatus} from 'js/account/stripe.api';

// check if the currently logged-in user has a paid subscription in an active status
// promise returns a boolean, or `null` if Stripe is not active - we check for the existence of `stripe_public_key`
export async function hasActiveSubscription() {
  await when(() => envStore.isReady);
  if (!envStore.data.stripe_public_key) {
    return null;
  }

  if (!subscriptionStore.isPending && !subscriptionStore.isInitialised) {
    subscriptionStore.fetchSubscriptionInfo();
  }

  await when(() => subscriptionStore.isInitialised);
  const plans = subscriptionStore.planResponse;
  if (!plans.length) {
    return false;
  }

  return (
    plans.filter(
      (sub) =>
        ACTIVE_STRIPE_STATUSES.includes(sub.status) &&
        sub.items?.[0].price.unit_amount > 0
    ).length > 0
  );
}

export function isAddonProduct(product: Product) {
  return product.metadata.product_type === 'addon';
}

export function isRecurringAddonProduct(product: Product) {
  return product.prices.some((price) => price?.recurring);
}

export function processCheckoutResponse(data: Checkout) {
  if (!data?.url) {
    notify.error(t('There has been an issue, please try again later.'));
  } else {
    window.location.assign(data.url);
  }
}

export async function processChangePlanResponse(data: ChangePlan) {
  switch (data.status) {
    case ChangePlanStatus.success:
      /**
        Wait a bit for the Stripe webhook to (hopefully) complete and the subscription list to update.
        We do this for 90% of use cases, since we can't tell on the frontend when the webhook has completed.
        The other 10% will be directed to refresh the page if the subscription isn't updated in the UI.
       */
      await new Promise((resolve) => setTimeout(resolve, 2000));
      processCheckoutResponse(data);
      location.reload();
      break;
    case ChangePlanStatus.scheduled:
      notify.success(
        t(
          'Success! Your subscription will change at the end of the current billing period.'
        )
      );
      break;
    default:
      notify.error(
        t(
          'There was an error processing your plan change. Please try again later.'
        )
      );
      break;
  }
  return data.status;
}

export function isChangeScheduled(
  price: BasePrice,
  subscriptions: SubscriptionInfo[]
) {
  return subscriptions.some((subscription) =>
    subscription.schedule?.phases?.some((phase) =>
      phase.items.some((item) => item.price === price.id)
    )
  );
}
